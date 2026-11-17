"""Minimal Bosch BME280 driver (Grove BME280) in forced mode.

Each :meth:`BME280.read` triggers one measurement, waits for it and applies
the floating-point compensation of the Bosch datasheet (BST-BME280-DS002,
section 8.1). Forced mode leaves the sensor asleep between readings, which
also limits self-heating.

Failures are explicit, never a zero:

- :class:`SensorUnavailable`: the device does not answer on the bus (unplugged,
  wrong address) or is not a BME280 (chip id).
- :class:`InvalidReading`: it answered, but with a "skipped" raw value, a
  measurement that never finished or a result outside the sensor's range.
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Any

ADDRESSES = (0x76, 0x77)
CHIP_ID = 0x60
BMP280_CHIP_ID = 0x58

REG_CALIB_TP = 0x88   # 26 bytes: T1..T3, P1..P9, (0xA0 unused), H1
REG_CALIB_H = 0xE1    # 7 bytes: H2..H6
REG_CHIP_ID = 0xD0
REG_RESET = 0xE0
REG_CTRL_HUM = 0xF2
REG_STATUS = 0xF3
REG_CTRL_MEAS = 0xF4
REG_CONFIG = 0xF5
REG_DATA = 0xF7       # 8 bytes: press[3], temp[3], hum[2]

OVERSAMPLING_X1 = 0b001
MODE_FORCED = 0b01
STATUS_MEASURING = 0x08

#: Raw values the chip outputs when a measurement was skipped.
SKIPPED_TP = 0x80000
SKIPPED_H = 0x8000

#: Operating range from the datasheet; outside it the value is not trusted.
RANGE_TEMPERATURE_C = (-40.0, 85.0)
RANGE_PRESSURE_HPA = (300.0, 1100.0)


class SensorUnavailable(Exception):
    """The sensor does not answer, or the device found is not a BME280."""


class InvalidReading(Exception):
    """The sensor answered with a value that cannot be trusted."""


@dataclass(frozen=True)
class Calibration:
    T1: int
    T2: int
    T3: int
    P1: int
    P2: int
    P3: int
    P4: int
    P5: int
    P6: int
    P7: int
    P8: int
    P9: int
    H1: int
    H2: int
    H3: int
    H4: int
    H5: int
    H6: int

    @classmethod
    def parse(cls, tp: bytes | list[int], h: bytes | list[int]) -> Calibration:
        tp, h = bytes(tp), bytes(h)
        if len(tp) != 26 or len(h) != 7:
            raise ValueError("calibration blocks must be 26 and 7 bytes")
        t1, t2, t3, p1, p2, p3, p4, p5, p6, p7, p8, p9 = struct.unpack("<HhhHhhhhhhhh", tp[:24])
        h1 = tp[25]
        h2, h3 = struct.unpack("<hB", h[:3])
        h4 = _signed12((h[3] << 4) | (h[4] & 0x0F))
        h5 = _signed12((h[5] << 4) | (h[4] >> 4))
        h6 = struct.unpack("<b", h[6:7])[0]
        return cls(t1, t2, t3, p1, p2, p3, p4, p5, p6, p7, p8, p9, h1, h2, h3, h4, h5, h6)


def _signed12(value: int) -> int:
    return value - 0x1000 if value & 0x800 else value


@dataclass(frozen=True)
class Measurement:
    temperature_c: float
    pressure_hpa: float
    humidity_percent: float


def compensate(cal: Calibration, adc_t: int, adc_p: int, adc_h: int) -> Measurement:
    """Datasheet double-precision compensation. Raises :class:`InvalidReading`."""
    if adc_t == SKIPPED_TP or adc_p == SKIPPED_TP or adc_h == SKIPPED_H:
        raise InvalidReading(f"measurement skipped by the sensor (raw T={adc_t:#x} P={adc_p:#x} H={adc_h:#x})")

    var1 = (adc_t / 16384.0 - cal.T1 / 1024.0) * cal.T2
    var2 = (adc_t / 131072.0 - cal.T1 / 8192.0) ** 2 * cal.T3
    t_fine = var1 + var2
    temperature = t_fine / 5120.0

    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * cal.P6 / 32768.0
    var2 = var2 + var1 * cal.P5 * 2.0
    var2 = var2 / 4.0 + cal.P4 * 65536.0
    var1 = (cal.P3 * var1 * var1 / 524288.0 + cal.P2 * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * cal.P1
    if var1 == 0:
        raise InvalidReading("pressure compensation divides by zero (bad calibration data)")
    pressure = 1048576.0 - adc_p
    pressure = (pressure - var2 / 4096.0) * 6250.0 / var1
    var1 = cal.P9 * pressure * pressure / 2147483648.0
    var2 = pressure * cal.P8 / 32768.0
    pressure = pressure + (var1 + var2 + cal.P7) / 16.0

    humidity = t_fine - 76800.0
    humidity = (adc_h - (cal.H4 * 64.0 + cal.H5 / 16384.0 * humidity)) * (
        cal.H2 / 65536.0 * (1.0 + cal.H6 / 67108864.0 * humidity * (1.0 + cal.H3 / 67108864.0 * humidity))
    )
    humidity = humidity * (1.0 - cal.H1 * humidity / 524288.0)
    humidity = min(100.0, max(0.0, humidity))

    result = Measurement(temperature, pressure / 100.0, humidity)
    _check_range("temperature", result.temperature_c, RANGE_TEMPERATURE_C, "degC")
    _check_range("pressure", result.pressure_hpa, RANGE_PRESSURE_HPA, "hPa")
    return result


def _check_range(name: str, value: float, bounds: tuple[float, float], unit: str) -> None:
    if not bounds[0] <= value <= bounds[1]:
        raise InvalidReading(f"{name} {value:.2f} {unit} outside the sensor range {bounds[0]:g}..{bounds[1]:g}")


class BME280:
    """One BME280 on an smbus-like ``bus``. Not thread-safe."""

    def __init__(self, bus: Any, address: int = 0x76, *, sleep=time.sleep,
                 measurement_timeout_s: float = 0.1) -> None:
        self.bus = bus
        self.address = address
        self._sleep = sleep
        self._timeout_s = measurement_timeout_s
        chip_id = self._io(bus.read_byte_data, address, REG_CHIP_ID)
        if chip_id != CHIP_ID:
            hint = " (that is a BMP280: no humidity)" if chip_id == BMP280_CHIP_ID else ""
            raise SensorUnavailable(f"device at {address:#04x} has chip id {chip_id:#04x}, not a BME280{hint}")
        self.calibration = Calibration.parse(
            self._io(bus.read_i2c_block_data, address, REG_CALIB_TP, 26),
            self._io(bus.read_i2c_block_data, address, REG_CALIB_H, 7),
        )
        # Filter off, standby irrelevant in forced mode.
        self._io(bus.write_byte_data, address, REG_CONFIG, 0x00)

    @classmethod
    def find(cls, bus: Any, addresses: tuple[int, ...] = ADDRESSES, **kwargs: Any) -> BME280:
        """First BME280 that answers at one of ``addresses``."""
        errors = []
        for address in addresses:
            try:
                return cls(bus, address, **kwargs)
            except SensorUnavailable as exc:
                errors.append(str(exc))
        raise SensorUnavailable("no BME280 found: " + "; ".join(errors))

    def _io(self, method: Any, *args: Any) -> Any:
        try:
            return method(*args)
        except OSError as exc:  # NACK / remote I/O error: nothing answers at that address
            raise SensorUnavailable(f"BME280 at {self.address:#04x} does not answer: {exc}") from exc

    def read(self) -> Measurement:
        bus, address = self.bus, self.address
        # ctrl_hum only takes effect after a write to ctrl_meas.
        self._io(bus.write_byte_data, address, REG_CTRL_HUM, OVERSAMPLING_X1)
        self._io(bus.write_byte_data, address, REG_CTRL_MEAS,
                 (OVERSAMPLING_X1 << 5) | (OVERSAMPLING_X1 << 2) | MODE_FORCED)
        # x1 oversampling on the three channels: at most 9.3 ms (datasheet 9.1).
        self._sleep(0.010)
        waited = 0.010
        while self._io(bus.read_byte_data, address, REG_STATUS) & STATUS_MEASURING:
            if waited >= self._timeout_s:
                raise InvalidReading(f"measurement not finished after {self._timeout_s:.2f} s")
            self._sleep(0.005)
            waited += 0.005
        data = self._io(bus.read_i2c_block_data, address, REG_DATA, 8)
        adc_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        adc_h = (data[6] << 8) | data[7]
        return compensate(self.calibration, adc_t, adc_p, adc_h)
