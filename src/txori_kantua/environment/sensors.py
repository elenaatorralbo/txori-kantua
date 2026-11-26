"""Read every environmental channel once, as dated samples with explicit quality.

A *source* is one physical sensor that yields one or more *channels*
(``bme280.pressure``...). A failed read never produces a number: the sample
keeps ``value=None`` and the quality of the MQTT contract (``unavailable``
when the sensor does not answer, ``error`` when it answers with a value that
fails validation). That is what lets a gap be told apart from a real zero.

Sources reconnect lazily: after a failure the next read opens the device
again, so plugging a sensor back in is observed without restarting.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .bme280 import BME280, InvalidReading, SensorUnavailable
from .grove_adc import AdcUnavailable, GroveAdc


class Unavailable(Exception):
    """Contract quality ``unavailable``: the sensor is absent or does not answer."""


class Invalid(Exception):
    """Contract quality ``error``: the sensor answered with an untrustworthy value."""


@dataclass(frozen=True)
class Channel:
    name: str
    metric: str
    unit: str
    #: Range the specific sensor can report; anything else is an ``error``.
    plausible: tuple[float, float]


@dataclass(frozen=True)
class Sample:
    channel: str
    metric: str
    unit: str
    utc: str
    elapsed_s: float
    value: float | None
    quality: str
    error: str | None = None

    def __post_init__(self) -> None:
        # The contract rule, enforced where samples are created.
        if (self.quality == "ok") != (self.value is not None):
            raise ValueError(f"inconsistent sample: quality {self.quality} with value {self.value}")


class Source:
    name: str
    channels: tuple[Channel, ...]

    def read(self) -> dict[str, float]:  # pragma: no cover - interface
        """Values by channel name. Raises :class:`Unavailable` or :class:`Invalid`."""
        raise NotImplementedError

    def close(self) -> None:
        pass


class Dht11Source(Source):
    """DHT11 on a GPIO (existing ``txori_kantua.dht11`` driver).

    The DHT11 datasheet range is 0..50 degC and 20..90 %RH. An all-zero frame
    passes the DHT11 checksum (0 + 0 + 0 + 0 == 0), so a stuck data line would
    look like "0 degC, 0 %"; the humidity range check turns it into an error.
    """

    name = "dht11"
    channels = (
        Channel("dht11.temperature", "temperature", "degC", (0.0, 50.0)),
        Channel("dht11.humidity", "humidity", "percent", (20.0, 90.0)),
    )

    def __init__(self, pin: int, factory: Callable[[int], Any] | None = None) -> None:
        self.pin = pin
        self._factory = factory
        self._driver: Any = None

    def _open(self) -> Any:
        if self._driver is None:
            factory = self._factory
            if factory is None:
                from txori_kantua.dht11 import DHT11 as factory  # needs lgpio (Pi only)
            try:
                self._driver = factory(self.pin)
            except Exception as exc:
                raise Unavailable(f"cannot open GPIO {self.pin}: {exc}") from exc
        return self._driver

    def read(self) -> dict[str, float]:
        driver = self._open()
        try:
            data = driver.read()
        except RuntimeError as exc:
            message = str(exc)
            # No pulses: nothing answered. Bad checksum: it answered, corrupted.
            if "checksum" in message:
                raise Invalid(message) from exc
            raise Unavailable(message) from exc
        return {"dht11.temperature": float(data["temperature"]), "dht11.humidity": float(data["humidity"])}

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            finally:
                self._driver = None


class Bme280Source(Source):
    name = "bme280"
    channels = (
        Channel("bme280.pressure", "pressure", "hPa", (300.0, 1100.0)),
        Channel("bme280.temperature", "temperature", "degC", (-40.0, 85.0)),
        Channel("bme280.humidity", "humidity", "percent", (0.0, 100.0)),
    )

    def __init__(self, bus: Any, addresses: tuple[int, ...] = (0x76, 0x77), **kwargs: Any) -> None:
        self.bus = bus
        self.addresses = addresses
        self._kwargs = kwargs
        self._sensor: BME280 | None = None

    @property
    def address(self) -> int | None:
        return self._sensor.address if self._sensor else None

    def read(self) -> dict[str, float]:
        try:
            if self._sensor is None:
                self._sensor = BME280.find(self.bus, self.addresses, **self._kwargs)
            m = self._sensor.read()
        except SensorUnavailable as exc:
            self._sensor = None  # find it again next time (replugged, power-cycled)
            raise Unavailable(str(exc)) from exc
        except InvalidReading as exc:
            raise Invalid(str(exc)) from exc
        return {"bme280.pressure": m.pressure_hpa, "bme280.temperature": m.temperature_c,
                "bme280.humidity": m.humidity_percent}


class LightSource(Source):
    """Grove light sensor on a Base Hat analogue port, in raw per mille (0..1000).

    The extra ``light.millivolts`` channel is evidence of what the ADC saw; it
    is not a contract metric.
    """

    name = "light"

    def __init__(self, bus: Any, channel: int = 0, addresses: tuple[int, ...] = (0x08, 0x04)) -> None:
        self.bus = bus
        self.adc_channel = channel
        self.addresses = addresses
        self._adc: GroveAdc | None = None
        self.channels = (
            Channel("light.raw", "light", "raw", (0.0, 1000.0)),
            Channel("light.millivolts", "light_voltage", "mV", (0.0, 3300.0)),
        )

    @property
    def product(self) -> str | None:
        return self._adc.product if self._adc else None

    def read(self) -> dict[str, float]:
        try:
            if self._adc is None:
                self._adc = GroveAdc.find(self.bus, self.addresses)
            ratio = self._adc.read_ratio(self.adc_channel)
            millivolts = self._adc.read_millivolts(self.adc_channel)
        except AdcUnavailable as exc:
            self._adc = None
            raise Unavailable(str(exc)) from exc
        return {"light.raw": float(ratio), "light.millivolts": float(millivolts)}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sample_all(sources: Sequence[Source], *, started: float,
               clock: Callable[[], float] = time.monotonic,
               utc: Callable[[], str] = _utc_now) -> list[Sample]:
    """One sample per channel of every source, failures included."""
    samples: list[Sample] = []
    for source in sources:
        stamp, elapsed = utc(), clock() - started
        try:
            values = source.read()
            if not isinstance(values, Mapping):
                raise Invalid("sensor returned no channel mapping")
            failure = None
        except Unavailable as exc:
            values, failure = {}, ("unavailable", str(exc))
        except Invalid as exc:
            values, failure = {}, ("error", str(exc))
        except OSError as exc:
            values, failure = {}, ("unavailable", str(exc))
        except (ValueError, TypeError, KeyError) as exc:
            values, failure = {}, ("error", str(exc))
        for channel in source.channels:
            common = dict(channel=channel.name, metric=channel.metric, unit=channel.unit,
                          utc=stamp, elapsed_s=round(elapsed, 3))
            if failure:
                samples.append(Sample(**common, value=None, quality=failure[0], error=failure[1]))
                continue
            value = values.get(channel.name)
            low, high = channel.plausible
            if value is None:
                samples.append(Sample(**common, value=None, quality="error", error="no value returned"))
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                samples.append(Sample(**common, value=None, quality="error", error="non-numeric reading"))
            elif not low <= value <= high:
                samples.append(Sample(**common, value=None, quality="error",
                                      error=f"{value:g} {channel.unit} outside {low:g}..{high:g}"))
            else:
                samples.append(Sample(**common, value=value, quality="ok"))
    return samples
