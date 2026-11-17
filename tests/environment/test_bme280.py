"""BME280 driver against the datasheet example and Bosch's integer reference."""

import pytest
from env_fakes import (
    ADC_H_EXAMPLE,
    ADC_P_EXAMPLE,
    ADC_T_EXAMPLE,
    H_EXAMPLE,
    FakeBme280,
    FakeBus,
    h_block,
    tp_block,
)

from txori_kantua.environment.bme280 import (
    BME280,
    Calibration,
    InvalidReading,
    SensorUnavailable,
    compensate,
)


def calibration(**h):
    return Calibration.parse(tp_block(), h_block(**{**H_EXAMPLE, **h}))


def humidity_int32_reference(cal, adc_t, adc_h):
    """BME280_compensate_H_int32 from the Bosch datasheet (section 4.2.3)."""
    var1 = ((adc_t >> 3) - (cal.T1 << 1)) * cal.T2 >> 11
    var2 = (((((adc_t >> 4) - cal.T1) * ((adc_t >> 4) - cal.T1)) >> 12) * cal.T3) >> 14
    t_fine = var1 + var2
    v = t_fine - 76800
    v = (((((adc_h << 14) - (cal.H4 << 20) - (cal.H5 * v)) + 16384) >> 15)
         * (((((((v * cal.H6) >> 10) * (((v * cal.H3) >> 11) + 32768)) >> 10) + 2097152) * cal.H2 + 8192) >> 14))
    v = v - (((((v >> 15) * (v >> 15)) >> 7) * cal.H1) >> 4)
    v = min(max(v, 0), 419430400)
    return (v >> 12) / 1024.0


def test_calibration_parsing_round_trips_signed_12_bit_fields():
    cal = calibration(H4=-200, H5=-3, H6=-7)
    assert (cal.T1, cal.T2, cal.T3, cal.P1, cal.P9) == (27504, 26435, -1000, 36477, 6000)
    assert (cal.H1, cal.H2, cal.H3, cal.H4, cal.H5, cal.H6) == (75, 362, 0, -200, -3, -7)


def test_temperature_and_pressure_match_the_datasheet_example():
    m = compensate(calibration(), ADC_T_EXAMPLE, ADC_P_EXAMPLE, ADC_H_EXAMPLE)
    assert m.temperature_c == pytest.approx(25.08, abs=0.01)
    assert m.pressure_hpa == pytest.approx(1006.5327, abs=0.001)


@pytest.mark.parametrize("adc_h", [20000, 30000, 40000, 50000])
def test_humidity_matches_bosch_integer_reference(adc_h):
    cal = calibration()
    m = compensate(cal, ADC_T_EXAMPLE, ADC_P_EXAMPLE, adc_h)
    assert m.humidity_percent == pytest.approx(humidity_int32_reference(cal, ADC_T_EXAMPLE, adc_h), abs=0.05)


@pytest.mark.parametrize("raw", [(0x80000, ADC_P_EXAMPLE, ADC_H_EXAMPLE),
                                 (ADC_T_EXAMPLE, 0x80000, ADC_H_EXAMPLE),
                                 (ADC_T_EXAMPLE, ADC_P_EXAMPLE, 0x8000)])
def test_skipped_measurement_is_an_error_not_a_value(raw):
    with pytest.raises(InvalidReading, match="skipped"):
        compensate(calibration(), *raw)


def test_all_zero_raw_data_is_rejected_by_range():
    # Bus pulled low: every byte reads 0. That must not become a reading.
    with pytest.raises(InvalidReading, match="outside the sensor range"):
        compensate(calibration(), 0, 0, 0)


def test_read_triggers_forced_mode_and_waits_for_the_measurement():
    chip = FakeBme280(busy_polls=2)
    sleeps = []
    sensor = BME280(FakeBus({0x76: chip}), sleep=sleeps.append)
    m = sensor.read()
    assert m.temperature_c == pytest.approx(25.08, abs=0.01)
    assert (0xF2, 0b001) in chip.writes
    assert (0xF4, 0b001_001_01) in chip.writes
    assert chip.writes.index((0xF2, 0b001)) < chip.writes.index((0xF4, 0b001_001_01))
    assert sleeps == [0.010, 0.005, 0.005]


def test_measurement_that_never_finishes_times_out():
    sensor = BME280(FakeBus({0x76: FakeBme280(busy_polls=10_000)}), sleep=lambda _s: None)
    with pytest.raises(InvalidReading, match="not finished"):
        sensor.read()


def test_find_probes_both_addresses():
    assert BME280.find(FakeBus({0x77: FakeBme280()})).address == 0x77


def test_absent_sensor_is_unavailable():
    with pytest.raises(SensorUnavailable, match="no BME280 found"):
        BME280.find(FakeBus())


def test_bmp280_is_not_accepted_as_bme280():
    with pytest.raises(SensorUnavailable, match="BMP280"):
        BME280(FakeBus({0x76: FakeBme280(chip_id=0x58)}), 0x76)


def test_unplugged_after_start_is_unavailable():
    bus = FakeBus({0x76: FakeBme280()})
    sensor = BME280(bus, sleep=lambda _s: None)
    bus.unplug(0x76)
    with pytest.raises(SensorUnavailable, match="does not answer"):
        sensor.read()
