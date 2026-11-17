"""Environmental sensor validation for issue #4.

    python -m txori_kantua.environment.env_check > report.md
    python -m txori_kantua.environment.env_check --phase covered --phase lit --phase-wait 30 > light.md
    python -m txori_kantua.environment.env_check --samples 10 --phase unplugged > disconnect.md

Every round reads the DHT11 (temperature, humidity), the BME280 (pressure,
plus its own temperature and humidity as a cross-check) and the Grove light
sensor through the Base Hat ADC. Each sample is dated (UTC and seconds since
start). A failed read is kept as a row with ``value`` empty and quality
``unavailable``/``error``, never as 0.

Phases are consecutive runs under different conditions (light covered/lit,
breath on the sensors, sensor unplugged). With more than one phase the
operator is prompted on stderr before each phase, the first included; the command waits for Enter on a terminal, or
``--phase-wait`` seconds otherwise (over a non-interactive SSH session).

The report goes to stdout as Markdown with the evidence header. Exit code 0
when every check passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from txori_kantua.audio.mic_check import header

from .i2c import DEFAULT_BUS, open_bus
from .sensors import Bme280Source, Dht11Source, LightSource, Sample, Source, sample_all

#: Acceptance criterion of #4: at least 30 dated readings per channel.
MIN_READINGS = 30
#: Smallest step each channel can show; below it a difference is not a response.
RESOLUTION = {
    "dht11.temperature": 1.0,   # DHT11 accuracy +-2 degC, integer steps on most units
    "dht11.humidity": 1.0,
    "bme280.pressure": 0.12,    # datasheet relative accuracy, hPa
    "bme280.temperature": 0.5,
    "bme280.humidity": 1.0,
    "light.raw": 5.0,
    "light.millivolts": 15.0,
}
#: Channels the issue asks to validate; the others are supporting evidence.
REQUIRED_CHANNELS = ("dht11.temperature", "dht11.humidity", "bme280.pressure", "light.raw")


@dataclass
class Phase:
    name: str
    rounds: list[list[Sample]] = field(default_factory=list)

    def samples(self, channel: str) -> list[Sample]:
        return [s for row in self.rounds for s in row if s.channel == channel]


def run_phase(name: str, sources: Sequence[Source], *, rounds: int, interval_s: float, started: float,
              clock: Callable[[], float] = time.monotonic,
              sleep: Callable[[float], None] = time.sleep) -> Phase:
    phase = Phase(name)
    next_tick = clock()
    for index in range(rounds):
        phase.rounds.append(sample_all(sources, started=started, clock=clock))
        if index + 1 < rounds:
            next_tick += interval_s
            sleep(max(0.0, next_tick - clock()))
    return phase


def _stderr_prompt(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


def wait_for_operator(name: str, wait_s: float, *, prompt: Callable[[str], None] = _stderr_prompt,
                      sleep: Callable[[float], None] = time.sleep, interactive: bool | None = None) -> None:
    if interactive is None:
        interactive = sys.stdin.isatty()
    if interactive:
        prompt(f">>> Next phase: '{name}'. Set the condition, then press Enter.")
        sys.stdin.readline()
        return
    prompt(f">>> Next phase: '{name}'. Set the condition now: starting in {wait_s:.0f} s.")
    sleep(wait_s)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _fmt(value: float | None, digits: int = 2) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def _stats(values: list[float]) -> tuple[float, float, float, float]:
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    return min(values), statistics.fmean(values), max(values), stdev


def summary_section(phases: Sequence[Phase], channels: Sequence[str]) -> str:
    lines = ["| Phase | Channel | ok | unavailable | error | Min | Mean | Max | Std dev | First failure |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for phase in phases:
        for channel in channels:
            samples = phase.samples(channel)
            values = [s.value for s in samples if s.value is not None]
            counts = {q: sum(1 for s in samples if s.quality == q) for q in ("ok", "unavailable", "error")}
            first = next((s.error for s in samples if s.error), "")
            if values:
                low, mean, high, stdev = _stats(values)
                numbers = f"{low:.2f} | {mean:.2f} | {high:.2f} | {stdev:.3f}"
            else:
                numbers = " | | | "
            unit = samples[0].unit if samples else ""
            lines.append(f"| {phase.name} | `{channel}` ({unit}) | {counts['ok']} | {counts['unavailable']} | "
                         f"{counts['error']} | {numbers} | {first.replace('|', '/')} |")
    return "\n".join(lines)


def response_section(phases: Sequence[Phase], channels: Sequence[str]) -> str:
    """Mean of each phase against the first one, with a noise-based threshold."""
    base = phases[0]
    lines = [f"Difference of each phase mean against `{base.name}`. A channel *responds* when the "
             "difference exceeds both 3 standard deviations of the noise and the sensor resolution.", "",
             "| Channel | " + " | ".join(p.name for p in phases) + " | Threshold | Response |",
             "|---|" + "---|" * len(phases) + "---|---|"]
    for channel in channels:
        series = [[s.value for s in p.samples(channel) if s.value is not None] for p in phases]
        if not series[0] or not any(series[1:]):
            lines.append(f"| `{channel}` | " + " | ".join(_fmt(statistics.fmean(v)) if v else "no data"
                                                          for v in series) + " | | not comparable |")
            continue
        noise = max((statistics.stdev(v) for v in series if len(v) > 1), default=0.0)
        threshold = max(3 * noise, RESOLUTION.get(channel, 0.0))
        base_mean = statistics.fmean(series[0])
        cells, responded = [_fmt(base_mean)], []
        for phase, values in zip(phases[1:], series[1:]):
            if not values:
                cells.append("no data")
                continue
            delta = statistics.fmean(values) - base_mean
            cells.append(f"{statistics.fmean(values):.2f} ({delta:+.2f})")
            if abs(delta) > threshold:
                responded.append(phase.name)
        verdict = ("**yes**: " + ", ".join(responded)) if responded else "no clear change"
        lines.append(f"| `{channel}` | " + " | ".join(cells) + f" | {threshold:.2f} | {verdict} |")
    return "\n".join(lines)


def samples_section(phase: Phase, channels: Sequence[str]) -> str:
    lines = ["| # | UTC | t (s) | " + " | ".join(f"`{c}`" for c in channels) + " |",
             "|---|---|---|" + "---|" * len(channels)]
    for index, row in enumerate(phase.rounds, start=1):
        by_channel = {s.channel: s for s in row}
        first = row[0] if row else None
        cells = []
        for channel in channels:
            sample = by_channel.get(channel)
            if sample is None:
                cells.append("")
            elif sample.value is None:
                cells.append(f"_{sample.quality}_")
            else:
                cells.append(_fmt(sample.value))
        lines.append(f"| {index} | {first.utc if first else ''} | {_fmt(first.elapsed_s, 1) if first else ''} | "
                     + " | ".join(cells) + " |")
    return "\n".join(lines)


def checks(phases: Sequence[Phase], channels: Sequence[str]) -> list[tuple[str, bool]]:
    result = []
    for channel in REQUIRED_CHANNELS:
        if channel not in channels:
            continue
        dated_ok = sum(1 for p in phases for s in p.samples(channel) if s.quality == "ok" and s.utc)
        result.append((f"`{channel}`: at least {MIN_READINGS} dated valid readings ({dated_ok})",
                       dated_ok >= MIN_READINGS))
    failed = [s for p in phases for row in p.rounds for s in row if s.quality != "ok"]
    result.append((f"Every failed read recorded as empty with explicit quality ({len(failed)} failed reads)",
                   all(s.value is None and s.error for s in failed)))
    return result


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m txori_kantua.environment.env_check",
                                description="Validate the environmental sensors (issue #4).")
    p.add_argument("--samples", type=int, default=MIN_READINGS, help="rounds per phase (default 30)")
    p.add_argument("--interval", type=float, default=2.0, help="seconds between rounds (DHT11 needs >= 1)")
    p.add_argument("--phase", action="append", dest="phases",
                   help="name of a condition; repeat for several (default: one 'baseline' phase)")
    p.add_argument("--phase-wait", type=float, default=30.0,
                   help="seconds to set up each phase when stdin is not a terminal")
    p.add_argument("--bus", type=int, default=DEFAULT_BUS, help="I2C bus number")
    p.add_argument("--dht-pin", type=int, default=5, help="DHT11 GPIO (BCM numbering)")
    p.add_argument("--light-channel", type=int, default=0, help="Base Hat analogue port (A0 -> 0)")
    p.add_argument("--bme280-address", type=lambda v: int(v, 0), action="append",
                   help="I2C address to probe (repeatable; default 0x76 and 0x77)")
    p.add_argument("--no-dht", action="store_true")
    p.add_argument("--no-bme280", action="store_true")
    p.add_argument("--no-light", action="store_true")
    return p


def build_sources(args: argparse.Namespace) -> list[Source]:
    sources: list[Source] = []
    if not args.no_dht:
        sources.append(Dht11Source(args.dht_pin))
    if not (args.no_bme280 and args.no_light):
        bus = open_bus(args.bus)
        if not args.no_bme280:
            sources.append(Bme280Source(bus, tuple(args.bme280_address or (0x76, 0x77))))
        if not args.no_light:
            sources.append(LightSource(bus, args.light_channel))
    return sources


def setup_section(args: argparse.Namespace, sources: Sequence[Source]) -> str:
    lines = [f"- Rounds per phase: {args.samples}, every {args.interval:g} s; phases: "
             + ", ".join(f"`{p}`" for p in args.phases)]
    for source in sources:
        if isinstance(source, Dht11Source):
            lines.append(f"- DHT11 on GPIO {source.pin} (BCM), driver `txori_kantua.dht11` (lgpio)")
        elif isinstance(source, Bme280Source):
            found = f"found at `{source.address:#04x}`" if source.address is not None else "**not found**"
            probed = ", ".join(f"{a:#04x}" for a in source.addresses)
            lines.append(f"- BME280 on I2C bus {args.bus}, {found} (probed {probed}); forced mode, "
                         "oversampling x1, filter off")
        elif isinstance(source, LightSource):
            found = source.product or "**ADC not found**"
            lines.append(f"- Grove light sensor on analogue port A{source.adc_channel}: {found}. "
                         "Value in **raw** per mille of the supply (0..1000), not lux")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, *,
         sources_factory: Callable[[argparse.Namespace], list[Source]] = build_sources,
         operator: Callable[[str, float], None] = wait_for_operator,
         sleep: Callable[[float], None] = time.sleep,
         clock: Callable[[], float] = time.monotonic) -> int:
    args = build_parser().parse_args(argv)
    args.phases = args.phases or ["baseline"]
    if args.samples < 1 or args.interval < 1.0:
        print("--samples must be >= 1 and --interval >= 1 s (DHT11 minimum period)", file=sys.stderr)
        return 2
    sources = sources_factory(args)
    if not sources:
        print("nothing to read: every sensor was disabled", file=sys.stderr)
        return 2

    phases: list[Phase] = []
    started = clock()
    try:
        for index, name in enumerate(args.phases):
            if index > 0 or len(args.phases) > 1:
                operator(name, args.phase_wait)
            print(f">>> Phase '{name}': {args.samples} rounds", file=sys.stderr, flush=True)
            phases.append(run_phase(name, sources, rounds=args.samples, interval_s=args.interval,
                                    started=started, clock=clock, sleep=sleep))
    finally:
        for source in sources:
            source.close()

    channels = [c.name for s in sources for c in s.channels]
    results = checks(phases, channels)
    title = "# Environmental sensors validation" + (f" — {', '.join(args.phases)}" if args.phases != ["baseline"] else "")
    sections = [title, "", header("#4", "txori_kantua.environment.env_check"), "",
                "## Setup", "", setup_section(args, sources), "",
                "## Summary", "", summary_section(phases, channels), ""]
    if len(phases) > 1:
        sections += ["## Response to condition changes", "", response_section(phases, channels), ""]
    for phase in phases:
        sections += [f"## Readings — {phase.name}", "", samples_section(phase, channels), ""]
    sections += ["## Result", "", "| Check | Result |", "|---|---|"]
    sections += [f"| {name} | {'PASS' if ok else '**FAIL**'} |" for name, ok in results]
    sections += ["", "## To fill in by hand", "",
                 "- Sensor models and Grove ports (photo of the wiring):",
                 "- Condition applied in each phase (what was covered, lit, unplugged, how):",
                 "- Reference values (room thermometer, nearby weather station pressure, luxmeter if any):",
                 "- Observations and limitations:", ""]
    print("\n".join(sections))
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
