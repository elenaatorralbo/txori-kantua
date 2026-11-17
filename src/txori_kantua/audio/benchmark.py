"""BirdNET feasibility benchmark on the Raspberry Pi 5 (issue #8).

    python -m txori_kantua.audio.benchmark fetch
    python -m txori_kantua.audio.benchmark run --model-dir DIR [--threads 1 2 4] > report.md
    python -m txori_kantua.audio.benchmark live --model FILE [--windows 20] > live.md

``run`` decodes the authorised corpus into memory, then for every combination
of model file and thread count measures load time, per-window inference
latency (p50/p95/max), peak resident memory, CPU time, temperature, clock and
throttling. It also reports what the model detected per recording, to check
that a fast configuration is not a broken one, and screens the corpus for
human voices. ``live`` runs capture (issue #7) and inference together to check
that inference keeps the capture pace without losing audio.

Reports are Markdown on stdout with the evidence header; ``--json`` saves the
raw numbers. No audio is written anywhere.
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from txori_kantua.privacy.log_guard import install as install_log_guard

from . import corpus as corpus_mod
from .birdnet import (
    HUMAN_LABELS,
    WINDOW_SECONDS,
    BirdNet,
    file_sha256,
    load_labels,
    pcm16_to_float32,
)

LOG = logging.getLogger("txori_kantua.benchmark")
SYS = Path("/")


# ---------------------------------------------------------------------------
# System probes (Linux / Raspberry Pi; every probe degrades to None)
# ---------------------------------------------------------------------------

def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def temperature_c(root: Path = SYS) -> float | None:
    value = _read(root / "sys/class/thermal/thermal_zone0/temp")
    return int(value) / 1000 if value and value.lstrip("-").isdigit() else None


def cpu_freq_mhz(root: Path = SYS) -> float | None:
    value = _read(root / "sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    return int(value) / 1000 if value and value.isdigit() else None


def throttled() -> str | None:
    """``vcgencmd get_throttled`` on a Pi; 0x0 means never throttled since boot."""
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip().removeprefix("throttled=") or None


def status_kb(field_name: str, root: Path = SYS) -> int | None:
    text = _read(root / "proc/self/status") or ""
    for line in text.splitlines():
        if line.startswith(field_name + ":"):
            return int(line.split()[1])
    return None


def mem_available_mb(root: Path = SYS) -> float | None:
    text = _read(root / "proc/meminfo") or ""
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024
    return None


def reset_peak_rss() -> bool:
    """Reset VmHWM so each configuration reports its own peak (Linux ≥ 4.0)."""
    try:
        Path("/proc/self/clear_refs").write_text("5")
        return True
    except OSError:
        return False


def percentile(values: Sequence[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q)) if values else float("nan")


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

@dataclass
class Budget:
    """Decision rule of ADR 0001: the model must leave the Pi room for the rest."""

    p95_s: float = 1.0          # ≤ one third of a 3 s window
    peak_rss_mb: float = 512.0  # ADR 0007 leaves the rest of RAM to the OS and services
    max_temp_c: float = 80.0    # Pi 5 firmware starts throttling at 80-85 °C

    def check(self, result: ConfigResult) -> list[str]:
        problems = []
        if not result.latencies_s:
            return ["no window was analysed"]
        if result.p95_s > self.p95_s:
            problems.append(f"p95 {result.p95_s:.3f} s > {self.p95_s} s")
        if result.peak_rss_mb is not None and result.peak_rss_mb > self.peak_rss_mb:
            problems.append(f"peak RSS {result.peak_rss_mb:.0f} MB > {self.peak_rss_mb:.0f} MB")
        if result.max_temp_c is not None and result.max_temp_c > self.max_temp_c:
            problems.append(f"temperature {result.max_temp_c:.1f} °C > {self.max_temp_c} °C")
        if result.throttled_after not in (None, "0x0"):
            problems.append(f"throttled={result.throttled_after}")
        return problems


@dataclass
class RecordingSummary:
    id: str
    species: str
    windows: int
    expected_top1: int = 0
    expected_max: float = 0.0
    human_max: float = 0.0
    top_species: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class ConfigResult:
    model: str
    precision: str
    version: str
    threads: int | None
    runtime: str
    load_s: float
    rss_after_load_mb: float | None
    latencies_s: list[float]
    cpu_s: float
    wall_s: float
    peak_rss_mb: float | None = None
    temps_c: list[float] = field(default_factory=list)
    freqs_mhz: list[float] = field(default_factory=list)
    throttled_before: str | None = None
    throttled_after: str | None = None
    recordings: list[RecordingSummary] = field(default_factory=list)

    @property
    def p50_s(self) -> float:
        return percentile(self.latencies_s, 50)

    @property
    def p95_s(self) -> float:
        return percentile(self.latencies_s, 95)

    @property
    def max_s(self) -> float:
        return max(self.latencies_s) if self.latencies_s else float("nan")

    @property
    def max_temp_c(self) -> float | None:
        return max(self.temps_c) if self.temps_c else None

    @property
    def cpu_cores(self) -> float:
        """Average cores busy during inference (1.0 = one core fully used)."""
        return self.cpu_s / self.wall_s if self.wall_s else 0.0


def run_config(
    model_path: Path,
    labels,
    corpus: list[tuple[corpus_mod.Recording, list[np.ndarray]]],
    *,
    threads: int | None,
    warmup: int = 2,
    min_confidence: float = 0.5,
    sustain_s: float = 0.0,
    realtime: bool = False,
    model_factory: Callable[..., BirdNet] = BirdNet,
    sha256: str | None = None,
) -> ConfigResult:
    gc.collect()
    reset_peak_rss()
    t0 = time.perf_counter()
    model = model_factory(model_path, labels, num_threads=threads)
    load_s = time.perf_counter() - t0
    rss = status_kb("VmRSS")
    result = ConfigResult(
        model=model_path.name, precision=model.precision, version=model.version(sha256),
        threads=threads, runtime=f"{model.runtime_name} {model.runtime_version}",
        load_s=load_s, rss_after_load_mb=rss / 1024 if rss else None,
        latencies_s=[], cpu_s=0.0, wall_s=0.0, throttled_before=throttled(),
    )
    first = next((w[0] for _, w in corpus if w), None)
    for _ in range(warmup if first is not None else 0):
        model.predict(first)

    def analyse(window: np.ndarray) -> np.ndarray:
        c0, w0 = time.process_time(), time.perf_counter()
        scores = model.predict(window)
        wall = time.perf_counter() - w0
        result.latencies_s.append(wall)
        result.cpu_s += time.process_time() - c0
        result.wall_s += wall
        for probe, bucket in ((temperature_c, result.temps_c), (cpu_freq_mhz, result.freqs_mhz)):
            value = probe()
            if value is not None:
                bucket.append(value)
        if realtime:
            time.sleep(max(0.0, WINDOW_SECONDS - wall))
        return scores

    for rec, wins in corpus:
        summary = RecordingSummary(rec.id, rec.species, len(wins))
        counts: dict[str, int] = {}
        for window in wins:
            scores = analyse(window)
            best = model.top(scores, k=1, min_confidence=min_confidence)
            if best:
                counts[best[0].scientific_name] = counts.get(best[0].scientific_name, 0) + 1
                if best[0].scientific_name == rec.species:
                    summary.expected_top1 += 1
            summary.expected_max = max(summary.expected_max, model.score_of(scores, frozenset({rec.species})))
            summary.human_max = max(summary.human_max, model.score_of(scores, HUMAN_LABELS))
        summary.top_species = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
        result.recordings.append(summary)

    # Optional sustained load: keep cycling the corpus to see thermal behaviour.
    deadline = time.monotonic() + sustain_s
    all_windows = [w for _, wins in corpus for w in wins]
    while sustain_s > 0 and all_windows and time.monotonic() < deadline:
        for window in all_windows:
            analyse(window)
            if time.monotonic() >= deadline:
                break

    peak = status_kb("VmHWM")
    result.peak_rss_mb = peak / 1024 if peak else None
    result.throttled_after = throttled()
    del model
    gc.collect()
    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _f(value: float | None, fmt: str = ".1f") -> str:
    return "n/a" if value is None or (isinstance(value, float) and np.isnan(value)) else format(value, fmt)


def results_table(results: Sequence[ConfigResult], budget: Budget) -> str:
    lines = [
        "| Model | Threads | Load (s) | p50 (ms) | p95 (ms) | Max (ms) | Real-time factor (p95) "
        "| CPU cores | Peak RSS (MB) | Temp max (°C) | Clock min (MHz) | Budget |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        problems = budget.check(r)
        rtf = WINDOW_SECONDS / r.p95_s if r.latencies_s and r.p95_s > 0 else float("nan")
        lines.append(
            f"| {r.precision} | {r.threads or 'default'} | {r.load_s:.2f} | {1000 * r.p50_s:.0f} | "
            f"{1000 * r.p95_s:.0f} | {1000 * r.max_s:.0f} | {_f(rtf, '.1f')}× | {r.cpu_cores:.2f} | "
            f"{_f(r.peak_rss_mb, '.0f')} | {_f(r.max_temp_c)} | {_f(min(r.freqs_mhz) if r.freqs_mhz else None, '.0f')} | "
            + ("meets" if not problems else "**" + "; ".join(problems) + "**") + " |")
    return "\n".join(lines)


def detections_table(result: ConfigResult, min_confidence: float) -> str:
    lines = [
        f"Model {result.precision}, threads {result.threads or 'default'}; top-1 species at score ≥ {min_confidence}.",
        "",
        "| Recording | Expected species | Windows | Expected is top-1 | Max score of expected | Most frequent top-1 | Max human-voice score |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in result.recordings:
        top = ", ".join(f"{name} ({n})" for name, n in s.top_species) or "none above threshold"
        lines.append(f"| {s.id} | *{s.species}* | {s.windows} | {s.expected_top1} | {s.expected_max:.2f} | "
                     f"{top} | {s.human_max:.2f} |")
    return "\n".join(lines)


def recommend(results: Sequence[ConfigResult], budget: Budget) -> str:
    passing = [r for r in results if not budget.check(r)]
    if not passing:
        return ("**No configuration meets the budget.** Options in ADR 0001: fewer threads with longer "
                "windows between analyses, the INT8 model, analysing every other window, or moving "
                "other services off the Pi. Audio stays local in every option.")
    best = min(passing, key=lambda r: (r.p95_s, r.peak_rss_mb or 0))
    return (f"Fastest configuration within budget: **{best.precision}, {best.threads or 'default'} threads** "
            f"(p95 {1000 * best.p95_s:.0f} ms = {100 * best.p95_s / WINDOW_SECONDS:.0f} % of a window). "
            "Prefer fewer threads if their p95 is also within budget: it leaves cores for capture, "
            "the broker and Grafana. The decision is recorded by a person in ADR 0001.")


def environment_lines() -> list[str]:
    from .mic_check import header

    lines = [header("#8", "txori_kantua.audio.benchmark")]
    lines.append(f"- **CPU cores:** {os.cpu_count()}; memory available at start: "
                 f"{_f(mem_available_mb(), '.0f')} MB; temperature at start: {_f(temperature_c())} °C; "
                 f"throttled: {throttled() or 'n/a (not a Pi)'}")
    return lines


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def _models(args: argparse.Namespace) -> list[Path]:
    models = [Path(m) for m in args.model or []]
    if args.model_dir:
        models += sorted(Path(args.model_dir).rglob("audio-model*.tflite"))
    if not models:
        raise SystemExit("give --model FILE or --model-dir DIR (see docs/birdnet-feasibility.md)")
    return models


def _labels_path(args: argparse.Namespace, model: Path) -> Path:
    if args.labels:
        return Path(args.labels)
    candidate = model.parent / "labels" / "en_us.txt"
    if not candidate.exists():
        raise SystemExit(f"labels not found next to {model}; use --labels")
    return candidate


def cmd_fetch(args: argparse.Namespace) -> int:
    recordings = corpus_mod.load_manifest()
    paths = corpus_mod.fetch(recordings, Path(args.cache))
    for rec, path in zip(recordings, paths):
        print(f"{rec.id}  {rec.species:26}  {rec.license:13}  {rec.author}  ->  {path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    models = _models(args)
    labels = load_labels(_labels_path(args, models[0]))
    recordings = corpus_mod.load_manifest()
    if args.limit:
        recordings = recordings[: args.limit]
    LOG.info("decoding %d recordings into memory", len(recordings))
    paths = corpus_mod.fetch(recordings, Path(args.cache))
    corpus = [(rec, list(corpus_mod.windows(corpus_mod.decode(path)))) for rec, path in zip(recordings, paths)]
    n_windows = sum(len(w) for _, w in corpus)
    budget = Budget(args.budget_p95, args.budget_rss, args.budget_temp)

    results: list[ConfigResult] = []
    for model in models:
        sha = file_sha256(model)
        for threads in args.threads:
            LOG.info("model %s, threads %s: %d windows", model.name, threads, n_windows)
            results.append(run_config(
                model, labels, corpus, threads=threads or None, warmup=args.warmup,
                min_confidence=args.min_confidence, sustain_s=args.sustain_seconds,
                realtime=args.realtime, sha256=sha))

    out = ["# BirdNET feasibility benchmark", "", *environment_lines(), ""]
    out += ["## Configuration", "",
            f"- Models: " + ", ".join(f"`{m.name}` (sha256 {file_sha256(m)[:12]})" for m in models),
            f"- Runtime: {results[0].runtime if results else 'n/a'}",
            f"- Corpus: {len(corpus)} recordings, **{n_windows} windows** of {WINDOW_SECONDS:g} s "
            f"(manifest `src/txori_kantua/audio/corpus.json` v1); warm-up {args.warmup} window(s) per configuration",
            f"- Pace: {'real time (one window every 3 s)' if args.realtime else 'back to back (worst case)'}"
            + (f"; sustained for {args.sustain_seconds:g} s after the corpus pass" if args.sustain_seconds else ""),
            f"- Budget (ADR 0001): p95 ≤ {budget.p95_s} s, peak RSS ≤ {budget.peak_rss_mb:.0f} MB, "
            f"temperature ≤ {budget.max_temp_c} °C, no throttling", ""]
    out += ["## Results", "", results_table(results, budget), "",
            "Latency is the wall time of one `invoke()` including the score sigmoid, excluding decoding. "
            "Peak RSS is the process high-water mark, reset before each configuration.", ""]
    out += ["## Recommendation", "", recommend(results, budget), ""]
    seen = set()
    out += ["## What the model detected", ""]
    for r in results:
        if r.precision in seen:
            continue
        seen.add(r.precision)
        out += [detections_table(r, args.min_confidence), ""]
    out += ["A human-voice score ≥ 0.10 in a recording would mean it should be replaced in the corpus "
            "(the corpus must not contain voices).", ""]
    out += ["## Corpus and licences", "",
            "| Id | Species | Author | Licence | Source |", "|---|---|---|---|---|"]
    out += [f"| {r.id} | *{r.species}* | {r.author} | [{r.license}]({r.license_url}) | [Commons]({r.page_url}) |"
            for r, _ in corpus]
    out += ["", "BirdNET V2.4 model: Kahl et al., Cornell Lab of Ornithology and Chemnitz University of "
            "Technology, https://doi.org/10.5281/zenodo.15050749, CC BY-NC 4.0.", ""]
    print("\n".join(out))

    if args.json:
        Path(args.json).write_text(json.dumps([
            {**asdict(r), "p50_s": r.p50_s, "p95_s": r.p95_s, "max_s": r.max_s, "budget": budget.check(r)}
            for r in results], indent=2))
    return 0 if any(not budget.check(r) for r in results) else 1


def cmd_live(args: argparse.Namespace) -> int:
    from .capture import ArecordStream, CaptureConfig, CaptureError
    from .devices import choose_device, usb_capture_cards

    model_path = _models(args)[0]
    labels = load_labels(_labels_path(args, model_path))
    model = BirdNet(model_path, labels, num_threads=args.threads[0] or None)
    device = args.device
    if device is None:
        cards = usb_capture_cards()
        if len(cards) != 1:
            raise SystemExit("choose the microphone with --device (see mic_check --list)")
        device, _ = choose_device(cards[0], 48000, 1, "S16_LE")
    config = CaptureConfig(device=device)
    latencies, birds, error = [], {}, None
    with ArecordStream(config) as stream:
        buffer = stream.new_buffer()
        for _ in range(args.windows):
            try:
                stream.read_window(buffer)
            except CaptureError as exc:
                error = str(exc)
                break
            t0 = time.perf_counter()
            scores = model.predict(pcm16_to_float32(buffer))
            latencies.append(time.perf_counter() - t0)
            # Species only: human classes are never reported (privacy.md).
            for cand in model.top(scores, k=3, min_confidence=args.min_confidence):
                birds[cand.scientific_name] = birds.get(cand.scientific_name, 0) + 1
        buffer[:] = bytes(len(buffer))
        overruns = stream.overruns
    print("\n".join(["# BirdNET live capture and inference", "", *environment_lines(), "",
                     f"- Device `{device}`, model {model.precision}, threads {args.threads[0] or 'default'}",
                     f"- Windows analysed: **{len(latencies)} / {args.windows}**" + (f"; error: `{error}`" if error else ""),
                     f"- Inference p50 {1000 * percentile(latencies, 50):.0f} ms, p95 {1000 * percentile(latencies, 95):.0f} ms "
                     f"per {WINDOW_SECONDS:g} s window",
                     f"- Capture overruns while inferring: **{overruns}** (0 means inference kept the capture pace)",
                     "- Species with score ≥ {:.2f}: {}".format(
                         args.min_confidence, ", ".join(f"*{k}* ({v})" for k, v in birds.items()) or "none"),
                     ""]))
    return 0 if error is None and overruns == 0 and len(latencies) == args.windows else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m txori_kantua.audio.benchmark",
                                description="BirdNET feasibility on the Raspberry Pi 5 (issue #8).")
    sub = p.add_subparsers(dest="command", required=True)

    def common(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--model", action="append", help="a BirdNET .tflite file (repeatable)")
        parser.add_argument("--model-dir", help="directory searched for audio-model*.tflite")
        parser.add_argument("--labels", help="labels file; default <model dir>/labels/en_us.txt")
        parser.add_argument("--threads", type=int, nargs="+", default=[0],
                            help="thread counts to try; 0 = runtime default")
        parser.add_argument("--min-confidence", type=float, default=0.5)

    fetch = sub.add_parser("fetch", help="download and verify the evaluation corpus")
    fetch.add_argument("--cache", default=str(corpus_mod.DEFAULT_CACHE))
    fetch.set_defaults(func=cmd_fetch)

    run = sub.add_parser("run", help="benchmark models on the corpus")
    common(run)
    run.add_argument("--cache", default=str(corpus_mod.DEFAULT_CACHE))
    run.add_argument("--limit", type=int, help="use only the first N recordings")
    run.add_argument("--warmup", type=int, default=2)
    run.add_argument("--sustain-seconds", type=float, default=0.0,
                     help="keep cycling the corpus this long to observe temperature")
    run.add_argument("--realtime", action="store_true", help="one window every 3 s, like the station")
    run.add_argument("--budget-p95", type=float, default=Budget.p95_s)
    run.add_argument("--budget-rss", type=float, default=Budget.peak_rss_mb)
    run.add_argument("--budget-temp", type=float, default=Budget.max_temp_c)
    run.add_argument("--json", help="also save the raw numbers to this file")
    run.set_defaults(func=cmd_run)

    live = sub.add_parser("live", help="capture from the microphone and infer in real time")
    common(live)
    live.add_argument("--device", help="ALSA device; default: the only USB capture card")
    live.add_argument("--windows", type=int, default=20)
    live.set_defaults(func=cmd_live)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    install_log_guard()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
