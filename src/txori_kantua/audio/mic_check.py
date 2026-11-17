"""USB microphone validation for issue #7.

    python -m txori_kantua.audio.mic_check --list
    python -m txori_kantua.audio.mic_check [--device D] [--windows 10] [--expect-tone 1000] > report.md
    python -m txori_kantua.audio.mic_check --disconnect-test [--reconnect-wait 60] > disconnect.md

The report goes to stdout as Markdown with the evidence header of
docs/evidence/README.md; operator prompts go to stderr. Audio is captured into
one reused RAM buffer and only level statistics are reported. After the run,
the privacy audit of issue #11 lists files created meanwhile and fails the
check if any of them looks like audio.

Exit code 0 when every check that ran passed, 1 otherwise, 2 on usage errors.
"""

from __future__ import annotations

import argparse
import logging
import math
import platform
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from txori_kantua.privacy.audit import DEFAULT_PATHS
from txori_kantua.privacy.detect import scan_tree
from txori_kantua.privacy.log_guard import install as install_log_guard

from .capture import (
    ArecordStream,
    CaptureConfig,
    CaptureError,
    WindowStats,
    window_stats,
)
from .devices import PROC_ASOUND, Card, choose_device, usb_capture_cards

StreamFactory = Callable[[CaptureConfig], ArecordStream]
MTIME_MARGIN_S = 1.0
LOG = logging.getLogger("txori_kantua.mic_check")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class WindowRow:
    index: int
    seconds: float
    stats: WindowStats | None
    error: str | None = None


@dataclass
class WindowRun:
    rows: list[WindowRow] = field(default_factory=list)
    elapsed_s: float = 0.0
    overruns: int = 0
    diagnostics: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[WindowRow]:
        return [r for r in self.rows if r.error]


@dataclass
class DisconnectResult:
    windows_before: int = 0
    error: str | None = None
    #: Time the failing read took to return; bounded by window + stall timeout.
    failing_read_s: float | None = None
    reopen_error: str | None = None
    reopen_s: float | None = None
    reconnected: bool | None = None
    reconnect_s: float | None = None


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def run_windows(factory: StreamFactory, config: CaptureConfig, count: int) -> WindowRun:
    """Capture ``count`` consecutive windows into one reused buffer."""
    run = WindowRun()
    started = time.monotonic()
    with factory(config) as stream:
        buffer = stream.new_buffer()
        for index in range(1, count + 1):
            t0 = time.monotonic()
            try:
                stream.read_window(buffer)
            except CaptureError as exc:
                run.rows.append(WindowRow(index, time.monotonic() - t0, None, str(exc)))
                break
            run.rows.append(WindowRow(index, time.monotonic() - t0, window_stats(buffer, config)))
        buffer[:] = bytes(len(buffer))  # overwrite before releasing the reference
        run.overruns = stream.overruns
        run.diagnostics = stream.diagnostics
    run.elapsed_s = time.monotonic() - started
    return run


def run_disconnect(
    factory: StreamFactory,
    config: CaptureConfig,
    *,
    max_wait_s: float,
    reconnect_wait_s: float,
    card_id: str | None,
    proc_root: Path = PROC_ASOUND,
    prompt: Callable[[str], None] = lambda text: print(text, file=sys.stderr, flush=True),
) -> DisconnectResult:
    result = DisconnectResult()
    deadline = time.monotonic() + max_wait_s
    with factory(config) as stream:
        buffer = stream.new_buffer()
        while time.monotonic() < deadline:
            t0 = time.monotonic()
            try:
                stream.read_window(buffer)
            except CaptureError as exc:
                result.error = f"{type(exc).__name__}: {exc}"
                result.failing_read_s = time.monotonic() - t0
                break
            result.windows_before += 1
            if result.windows_before == 1:
                prompt(f">>> Capturing. UNPLUG the microphone now (waiting up to {max_wait_s:.0f} s).")
        buffer[:] = bytes(len(buffer))
    if result.error is None:
        return result

    # Opening a device that is absent must fail promptly, not hang.
    t0 = time.monotonic()
    try:
        with factory(config) as stream:
            stream.read_window()
        result.reopen_error = None
    except CaptureError as exc:
        result.reopen_error = f"{type(exc).__name__}: {exc}"
    result.reopen_s = time.monotonic() - t0

    if reconnect_wait_s > 0 and card_id is not None:
        prompt(f">>> PLUG the microphone back in (waiting up to {reconnect_wait_s:.0f} s).")
        t0 = time.monotonic()
        result.reconnected = False
        while time.monotonic() - t0 < reconnect_wait_s:
            if any(c.card_id == card_id for c in usb_capture_cards(proc_root)):
                time.sleep(1.0)  # let udev finish setting permissions
                try:
                    with factory(config) as stream:
                        stream.read_window()
                    result.reconnected = True
                except CaptureError:
                    time.sleep(0.5)
                    continue
                break
            time.sleep(0.5)
        result.reconnect_s = time.monotonic() - t0
    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _probe(*command: str) -> str:
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return "not available"
    return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else "not available"


def _read(path: str) -> str:
    try:
        return Path(path).read_text().replace("\0", "").strip()
    except OSError:
        return "not available"


def _os_name() -> str:
    for line in _read("/etc/os-release").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip('"')
    return "not available"


def header(issue: str, module: str = "txori_kantua.audio.mic_check") -> str:
    repo = Path(__file__).resolve().parents[3]
    commit = _probe("git", "-C", str(repo), "rev-parse", "--short", "HEAD")
    dirty = _probe("git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no")
    if dirty not in ("", "not available"):
        commit += " (with local changes)"
    return "\n".join([
        f"- **Date (UTC):** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        "- **Run by:** _fill in_",
        "- **Reviewed by:** _fill in_",
        f"- **Issue / PR:** {issue} / _fill in_",
        f"- **Commit:** {commit}",
        f"- **Hardware:** {_read('/proc/device-tree/model')}; {_os_name()}; {platform.machine()}",
        f"- **Relevant versions:** Python {platform.python_version()}; kernel {platform.release()}; "
        f"{_probe('arecord', '--version')}",
        f"- **Procedure:** `python -m {module} {' '.join(sys.argv[1:])}`",
    ])


def _fmt_db(value: float) -> str:
    return "-inf" if math.isinf(value) else f"{value:.1f}"


def card_table(cards: Sequence[Card]) -> str:
    if not cards:
        return "No USB capture device found in `/proc/asound`."
    lines = ["| Card | ALSA name | USB id | Name | Native capture formats |", "|---|---|---|---|---|"]
    for card in cards:
        formats = "<br>".join(f.describe() for f in card.capture_formats)
        lines.append(f"| {card.index} | `{card.hw}` | {card.usb_id or '?'} | "
                     f"{card.long_name or card.name} | {formats} |")
    return "\n".join(lines)


def windows_section(run: WindowRun, config: CaptureConfig, expect_tone: float | None) -> tuple[str, bool]:
    lines = ["| # | Read time (s) | Peak dBFS | RMS dBFS | Clipped % | DC offset | Tone est. (Hz) | Status |",
             "|---|---|---|---|---|---|---|---|"]
    ok_rows = 0
    for row in run.rows:
        if row.stats is None:
            lines.append(f"| {row.index} | {row.seconds:.2f} | | | | | | **ERROR** {row.error} |")
            continue
        s = row.stats
        notes = []
        if s.silent:
            notes.append("silent")
        if s.clipping:
            notes.append("clipping")
        if expect_tone and not s.silent:
            if abs(s.zero_crossing_hz - expect_tone) > 0.05 * expect_tone:
                notes.append("tone mismatch")
        status = "ok" if not notes else ", ".join(notes)
        ok_rows += 1
        lines.append(f"| {row.index} | {row.seconds:.2f} | {_fmt_db(s.peak_dbfs)} | {_fmt_db(s.rms_dbfs)} | "
                     f"{100 * s.clipped_fraction:.3f} | {s.dc_offset:+.4f} | {s.zero_crossing_hz:.0f} | {status} |")
    expected = len(run.rows) * config.window_seconds
    drift = (run.elapsed_s - expected) / expected * 100 if expected else 0.0
    lines += [
        "",
        f"- Windows captured without error: **{ok_rows} / {len(run.rows)}**",
        f"- Total time {run.elapsed_s:.2f} s for {expected:.1f} s of audio ({drift:+.1f} %; the first "
        "read includes device start-up)",
        f"- Overruns reported by arecord: {run.overruns}",
    ]
    if run.diagnostics:
        lines.append("- arecord messages: " + "; ".join(f"`{d}`" for d in run.diagnostics[-5:]))
    return "\n".join(lines), not run.errors


def privacy_section(since: float, paths: Sequence[str]) -> tuple[str, bool]:
    scan = scan_tree(paths, newer_than=since)
    lines = [
        f"Scanned {', '.join(f'`{p}`' for p in paths)}: {scan.files_checked} files, "
        f"{scan.unreadable} unreadable entries" + (" (run with sudo for full coverage)" if scan.unreadable else "") + ".",
        "",
        f"- Files created or modified during the run: {len(scan.new_files)}",
    ]
    lines += [f"  - `{p}`" for p in scan.new_files[:20]]
    if len(scan.new_files) > 20:
        lines.append(f"  - ... and {len(scan.new_files) - 20} more")
    created = set(scan.new_files)
    during = [f for f in scan.findings if f.location in created]
    before = [f for f in scan.findings if f.location not in created]
    if during:
        lines.append("- **Audio-like files created during the run:**")
        lines += [f"  - `{f.location}`: {f.reason}" for f in during]
    else:
        lines.append("- Audio-like files created during the run: none")
    if before:
        # Not caused by this capture, but still audio on disk: review them.
        lines.append(f"- Pre-existing audio-like files (older than the run, review separately): {len(before)}")
        lines += [f"  - `{f.location}`: {f.reason}" for f in before[:20]]
    return "\n".join(lines), not during


def disconnect_section(result: DisconnectResult, config: CaptureConfig) -> tuple[str, bool]:
    bound = config.window_seconds + config.stall_timeout_s + 1.0
    lines = [f"- Windows captured before the disconnection: {result.windows_before}"]
    if result.error is None:
        lines.append("- **No disconnection observed** within the waiting time.")
        return "\n".join(lines), False
    detected = result.failing_read_s is not None and result.failing_read_s <= bound
    reopened = result.reopen_error is not None and (result.reopen_s or 0) <= bound
    lines += [
        f"- Detected as: `{result.error}`",
        f"- The failing read returned after {result.failing_read_s:.2f} s (bound {bound:.1f} s): "
        + ("ok" if detected else "**too slow**"),
        f"- Reopening while absent failed after {result.reopen_s:.2f} s: "
        + (f"`{result.reopen_error}`" if result.reopen_error else "**it did not fail**"),
    ]
    passed = detected and reopened
    if result.reconnected is not None:
        lines.append(f"- After plugging back in: "
                     + (f"captured a window after {result.reconnect_s:.1f} s" if result.reconnected
                        else f"**not recovered** after {result.reconnect_s:.1f} s"))
        passed = passed and result.reconnected
    lines.append("- The application did not block: this report was written after the disconnection.")
    return "\n".join(lines), passed


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m txori_kantua.audio.mic_check",
                                description="Validate USB microphone capture into RAM (issue #7).")
    p.add_argument("--list", action="store_true", help="list USB capture devices and exit")
    p.add_argument("--device", help="ALSA device; default: the only USB capture card")
    p.add_argument("--windows", type=int, default=10)
    p.add_argument("--seconds", type=float, default=3.0, help="window length (BirdNET uses 3 s)")
    p.add_argument("--rate", type=int, default=48000)
    p.add_argument("--channels", type=int, default=1)
    p.add_argument("--format", default="S16_LE", choices=("S16_LE", "S32_LE"))
    p.add_argument("--stall-timeout", type=float, default=2.0)
    p.add_argument("--expect-tone", type=float, help="frequency of the test tone played, in Hz")
    p.add_argument("--disconnect-test", action="store_true")
    p.add_argument("--max-wait", type=float, default=60.0, help="seconds to wait for the unplug")
    p.add_argument("--reconnect-wait", type=float, default=0.0,
                   help="seconds to wait for the device to be plugged back in (0 skips)")
    p.add_argument("--scan", nargs="*", default=list(DEFAULT_PATHS),
                   help="paths checked for new audio files after the run")
    return p


def main(argv: Sequence[str] | None = None, *, factory: StreamFactory = ArecordStream,
         proc_root: Path = PROC_ASOUND) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    install_log_guard()
    args = build_parser().parse_args(argv)
    cards = usb_capture_cards(proc_root)

    if args.list:
        print(card_table(cards))
        return 0

    card = None
    if args.device:
        device, converted = args.device, args.device.startswith("plug")
        card = next((c for c in cards if f"CARD={c.card_id}," in args.device), None)
    elif len(cards) == 1:
        card = cards[0]
        device, converted = choose_device(card, args.rate, args.channels, args.format)
    else:
        print(card_table(cards), file=sys.stderr)
        print("Choose one with --device." if cards else "Connect the USB microphone.", file=sys.stderr)
        return 2

    config = CaptureConfig(device=device, rate=args.rate, channels=args.channels,
                           sample_format=args.format, window_seconds=args.seconds,
                           stall_timeout_s=args.stall_timeout)
    issue = "#7"
    sections = [f"# USB microphone validation{' — disconnection' if args.disconnect_test else ''}",
                "", header(issue), ""]
    sections += ["## Device", "", card_table([card] if card else cards), ""]
    sections += ["## Configuration", "",
                 f"- ALSA device opened: `{config.device}`"
                 + (" (ALSA converts from the native format)" if converted else " (native format, no conversion)"),
                 f"- {config.sample_format}, {config.channels} channel(s), {config.rate} Hz, "
                 f"{config.window_seconds:g} s windows = {config.window_bytes} bytes in one reused RAM buffer",
                 f"- Stall timeout: {config.stall_timeout_s:g} s", ""]

    checks: list[tuple[str, bool]] = []
    # File mtimes come from the kernel's coarse clock, which can lag time.time()
    # by a few milliseconds: without a margin, a file written right after the
    # start would look older than the run and escape the check.
    since = time.time() - MTIME_MARGIN_S
    if args.disconnect_test:
        result = run_disconnect(factory, config, max_wait_s=args.max_wait,
                                reconnect_wait_s=args.reconnect_wait,
                                card_id=card.card_id if card else None, proc_root=proc_root)
        text, ok = disconnect_section(result, config)
        sections += ["## Disconnection", "", text, ""]
        checks.append(("Disconnection detected without blocking", ok))
    else:
        LOG.info("capturing %d windows of %g s from %s", args.windows, args.seconds, device)
        run = run_windows(factory, config, args.windows)
        text, ok = windows_section(run, config, args.expect_tone)
        sections += ["## Windows", "", text, ""]
        checks.append((f"{args.windows} consecutive windows without error", ok and len(run.rows) == args.windows))

    text, ok = privacy_section(since, args.scan)
    sections += ["## Persistent audio files (issue #11 audit)", "", text, ""]
    checks.append(("No audio file created by the capture", ok))

    sections += ["## Result", "", "| Check | Result |", "|---|---|"]
    sections += [f"| {name} | {'PASS' if ok else '**FAIL**'} |" for name, ok in checks]
    sections += ["", "## To fill in by hand", "",
                 "- Microphone and USB interface model:",
                 "- Test sound (source, frequency, approximate level and distance):",
                 "- Room and background noise:",
                 "- Observations and limitations:", ""]
    print("\n".join(sections))
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
