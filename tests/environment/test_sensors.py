"""Samples per channel: dated, with explicit quality and never an invented zero."""

import pytest
from env_fakes import FakeAdc, FakeBme280, FakeBus

from txori_kantua.environment.grove_adc import AdcUnavailable, GroveAdc
from txori_kantua.environment.sensors import (
    Bme280Source,
    Dht11Source,
    LightSource,
    Sample,
    sample_all,
)


class FakeDht:
    def __init__(self, results):
        self.results = list(results)
        self.closed = False

    def read(self):
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        self.closed = True


def by_channel(samples):
    return {s.channel: s for s in samples}


def sample(sources):
    return by_channel(sample_all(sources, started=0.0, clock=lambda: 1.5, utc=lambda: "2026-11-17T10:00:00.000Z"))


def test_sample_rejects_a_value_with_failed_quality():
    with pytest.raises(ValueError):
        Sample("x", "temperature", "degC", "t", 0.0, 0.0, "error", "boom")
    with pytest.raises(ValueError):
        Sample("x", "temperature", "degC", "t", 0.0, None, "ok")


def test_dht11_ok_reading_is_dated():
    source = Dht11Source(5, factory=lambda pin: FakeDht([{"temperature": 21.0, "humidity": 48.0}]))
    s = sample([source])
    assert s["dht11.temperature"].value == 21.0
    assert s["dht11.humidity"].quality == "ok"
    assert s["dht11.temperature"].utc == "2026-11-17T10:00:00.000Z"
    assert s["dht11.temperature"].elapsed_s == 1.5


def test_dht11_without_pulses_is_unavailable_and_bad_checksum_is_error():
    source = Dht11Source(5, factory=lambda pin: FakeDht([RuntimeError("DHT11: only 0 pulses received"),
                                                         RuntimeError("DHT11: bad checksum [1, 2, 3, 4, 0]")]))
    first, second = sample([source]), sample([source])
    assert (first["dht11.temperature"].quality, first["dht11.temperature"].value) == ("unavailable", None)
    assert (second["dht11.humidity"].quality, second["dht11.humidity"].value) == ("error", None)


def test_dht11_all_zero_frame_is_not_a_valid_zero():
    # 0,0,0,0 has a valid checksum: a stuck line would otherwise read "0 degC, 0 %".
    source = Dht11Source(5, factory=lambda pin: FakeDht([{"temperature": 0.0, "humidity": 0.0}]))
    s = sample([source])
    assert s["dht11.humidity"].quality == "error"
    assert s["dht11.humidity"].value is None
    assert "outside" in s["dht11.humidity"].error


def test_dht11_gpio_that_cannot_be_opened_is_unavailable():
    def broken(pin):
        raise OSError("GPIO busy")

    s = sample([Dht11Source(5, factory=broken)])
    assert s["dht11.temperature"].quality == "unavailable"
    assert "GPIO busy" in s["dht11.temperature"].error


def test_bme280_unplug_and_replug_is_observed_without_restart():
    bus = FakeBus({0x76: FakeBme280()})
    source = Bme280Source(bus, sleep=lambda _s: None)
    assert sample([source])["bme280.pressure"].value == pytest.approx(1006.53, abs=0.01)
    chip = bus.unplug(0x76)
    unplugged = sample([source])
    assert {s.quality for s in unplugged.values()} == {"unavailable"}
    assert all(s.value is None for s in unplugged.values())
    bus.plug(0x76, chip)
    assert sample([source])["bme280.pressure"].quality == "ok"


def test_light_is_raw_per_mille_with_voltage_as_evidence():
    s = sample([LightSource(FakeBus({0x04: FakeAdc(ratio=420, millivolts=1386)}))])
    assert (s["light.raw"].value, s["light.raw"].unit) == (420.0, "raw")
    assert s["light.millivolts"].value == 1386.0


def test_light_adc_absent_is_unavailable():
    s = sample([LightSource(FakeBus())])
    assert s["light.raw"].quality == "unavailable"
    assert s["light.raw"].value is None


def test_adc_rejects_unknown_product_and_channel():
    with pytest.raises(AdcUnavailable, match="product id"):
        GroveAdc(FakeBus({0x08: FakeAdc(product=0x1234)}), 0x08)
    adc = GroveAdc.find(FakeBus({0x08: FakeAdc()}))
    assert adc.address == 0x08
    with pytest.raises(ValueError):
        adc.read_ratio(9)


def test_one_failing_source_does_not_hide_the_others():
    bus = FakeBus({0x08: FakeAdc()})
    s = sample([Bme280Source(bus), LightSource(bus)])
    assert s["bme280.pressure"].quality == "unavailable"
    assert s["light.raw"].quality == "ok"
