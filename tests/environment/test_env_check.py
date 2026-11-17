"""The env_check report: phases, response detection and the #4 checks."""

from env_fakes import FakeAdc, FakeBme280, FakeBus

from txori_kantua.environment import env_check
from txori_kantua.environment.sensors import Bme280Source, Dht11Source, LightSource


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class SteadyDht:
    def __init__(self, _pin):
        pass

    def read(self):
        return {"temperature": 21.0, "humidity": 50.0}

    def close(self):
        pass


def run(argv, factory, phase_hook=None):
    clock = Clock()
    seen = []

    def operator(name, wait):
        seen.append(name)
        if phase_hook:
            phase_hook(name)

    code = env_check.main(argv, sources_factory=factory, operator=operator, sleep=clock.sleep, clock=clock)
    return code, seen, clock


def test_baseline_run_passes_with_30_readings_per_channel(capsys):
    bus = FakeBus({0x76: FakeBme280(), 0x08: FakeAdc()})

    def factory(args):
        return [Dht11Source(5, factory=SteadyDht), Bme280Source(bus, sleep=lambda _s: None), LightSource(bus)]

    code, seen, clock = run([], factory)
    report = capsys.readouterr().out
    assert code == 0
    assert seen == []
    assert clock.now == 29 * 2.0
    assert "`dht11.temperature`: at least 30 dated valid readings (30) | PASS" in report
    assert "`light.raw`: at least 30 dated valid readings (30) | PASS" in report
    assert "found at `0x76`" in report
    assert "## Readings — baseline" in report


def test_light_response_between_two_phases_is_detected(capsys):
    adc = FakeAdc(ratio=80)
    bus = FakeBus({0x08: adc})

    def lit(name):
        if name == "lit":
            adc.ratio[0] = 650

    code, seen, _ = run(["--no-dht", "--no-bme280", "--samples", "5", "--phase", "covered", "--phase", "lit"],
                        lambda args: [LightSource(bus)], phase_hook=lit)
    report = capsys.readouterr().out
    assert seen == ["covered", "lit"]
    assert "| `light.raw` | 80.00 | 650.00 (+570.00) |" in report
    assert "**yes**: lit" in report
    assert code == 1  # 10 readings: below the 30 the issue requires


def test_unplugged_sensor_is_reported_as_failures_never_zero(capsys):
    bus = FakeBus({0x76: FakeBme280()})

    def unplug(name):
        if name == "unplugged":
            bus.unplug(0x76)

    code, _, _ = run(["--no-dht", "--no-light", "--samples", "30", "--phase", "plugged", "--phase", "unplugged"],
                     lambda args: [Bme280Source(bus, sleep=lambda _s: None)], phase_hook=unplug)
    report = capsys.readouterr().out
    assert "| unplugged | `bme280.pressure` (hPa) | 0 | 30 | 0 |" in report
    assert "_unavailable_" in report
    assert "| 0.00 |" not in report
    assert "Every failed read recorded as empty with explicit quality (90 failed reads) | PASS" in report
    assert code == 0


def test_interval_below_dht11_minimum_is_a_usage_error():
    assert env_check.main(["--interval", "0.5"], sources_factory=lambda a: []) == 2
