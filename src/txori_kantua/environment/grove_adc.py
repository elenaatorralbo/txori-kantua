"""ADC of the Seeed Grove Base Hat for Raspberry Pi (analogue ports A0..A6).

The Hat carries a microcontroller that samples its analogue ports and exposes
them over I2C. Register map, as used by Seeed's ``grove.py`` driver:

- ``0x00``: product id (``0x0004`` Base Hat, ``0x0005`` Base Hat for Pi Zero)
- ``0x10 + ch``: raw 12-bit value
- ``0x20 + ch``: input voltage in mV
- ``0x30 + ch``: voltage / supply in per mille (0..1000)

The Grove light sensor (photoresistor divider) gives a voltage that rises
with light. That voltage is **not** lux: converting it needs the exact sensor
curve and a calibration against a luxmeter, so it is reported as ``raw``.
"""

from __future__ import annotations

from typing import Any

ADDRESSES = (0x08, 0x04)  # newer firmware answers at 0x08, older at 0x04
PRODUCT_IDS = {0x0004: "Grove Base Hat for Raspberry Pi", 0x0005: "Grove Base Hat for Raspberry Pi Zero"}
REG_PRODUCT_ID = 0x00
REG_RAW = 0x10
REG_VOLTAGE = 0x20
REG_RATIO = 0x30
CHANNELS = range(8)


class AdcUnavailable(Exception):
    """The Base Hat ADC does not answer on the bus."""


class GroveAdc:
    def __init__(self, bus: Any, address: int) -> None:
        self.bus = bus
        self.address = address
        product = self._register(REG_PRODUCT_ID)
        if product not in PRODUCT_IDS:
            raise AdcUnavailable(f"device at {address:#04x} has product id {product:#06x}, not a Grove Base Hat")
        self.product = PRODUCT_IDS[product]

    @classmethod
    def find(cls, bus: Any, addresses: tuple[int, ...] = ADDRESSES) -> GroveAdc:
        errors = []
        for address in addresses:
            try:
                return cls(bus, address)
            except AdcUnavailable as exc:
                errors.append(str(exc))
        raise AdcUnavailable("no Grove Base Hat ADC found: " + "; ".join(errors))

    def _register(self, register: int) -> int:
        try:
            self.bus.write_byte(self.address, register)
            return self.bus.read_word_data(self.address, register)
        except OSError as exc:
            raise AdcUnavailable(f"Base Hat ADC at {self.address:#04x} does not answer: {exc}") from exc

    def _channel(self, base: int, channel: int) -> int:
        if channel not in CHANNELS:
            raise ValueError(f"channel must be 0..7, got {channel}")
        return self._register(base + channel)

    def read_raw(self, channel: int) -> int:
        return self._channel(REG_RAW, channel)

    def read_millivolts(self, channel: int) -> int:
        return self._channel(REG_VOLTAGE, channel)

    def read_ratio(self, channel: int) -> int:
        """Per mille of the supply voltage (0..1000)."""
        return self._channel(REG_RATIO, channel)
