"""Privacy audit command line (issue #11).

    python -m txori_kantua.privacy.audit system [--pid PID]
    python -m txori_kantua.privacy.audit files [--since T] [--allow-manifest M] [PATH ...]
    python -m txori_kantua.privacy.audit payloads [--mqtt] [FILE]
    python -m txori_kantua.privacy.audit control DIR

Every subcommand prints Markdown that can be pasted into an evidence report
and exits 0 when nothing was found, 1 when something needs review and 2 on a
usage error. The audit reads and reports; it never deletes what it finds
(except the control file it creates itself) so the evidence is preserved.

``control`` proves the procedure works: it plants a synthetic tone file and a
payload carrying base64 audio, checks that both are reported, and removes its
own file. Run it before trusting a clean ``files`` or ``payloads`` result.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import secrets
import struct
import sys
import time
import wave
from collections.abc import Iterable, Sequence
from pathlib import Path

from .detect import Finding, inspect_payload, scan_tree
from .system import Status, run_checks

#: Places a capture or inference process could leave audio behind on the Pi.
DEFAULT_PATHS = (
    "/tmp",
    "/var/tmp",
    "/dev/shm",
    "/run/txori-kantua",
    "/var/lib/txori-kantua",
    "/opt/txori-kantua",
    "/var/log",
    "/var/lib/systemd/coredump",
    "/var/backups",
    str(Path.home()),
)


# ---------------------------------------------------------------------------
# Synthetic control material (a generated tone, never a recording)
# ---------------------------------------------------------------------------

def synthetic_wav(seconds: float = 0.25, rate: int = 16000, freq: float = 1000.0) -> bytes:
    """A short generated sine tone as WAV bytes. Contains no recorded sound."""
    frames = int(seconds * rate)
    samples = (int(12000 * math.sin(2 * math.pi * freq * i / rate)) for i in range(frames))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    return buffer.getvalue()


def control_payload() -> bytes:
    """A detection-shaped message that smuggles base64 audio in an extra field."""
    event = {
        "schema_version": "1.0",
        "event_id": "00000000-0000-4000-8000-00000000c0de",
        "station_id": "privacy-control",
        "observed_at": "2026-01-01T00:00:00Z",
        "window_end": "2026-01-01T00:00:03Z",
        "species": {"scientific_name": "Turdus merula"},
        "confidence": 0.5,
        "model": {"name": "control", "version": "control"},
        "clip": base64.b64encode(synthetic_wav()).decode("ascii"),
    }
    return json.dumps(event).encode("utf-8")


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def _table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(lines)


def _findings_table(findings: Sequence[Finding]) -> str:
    if not findings:
        return "No findings."
    return _table(("Location", "Reason"), ((f"`{f.location}`", f.reason) for f in findings))


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_system(args: argparse.Namespace) -> int:
    checks = run_checks(Path(args.root), pid=args.pid)
    print("## Memory persistence checks\n")
    print(_table(("Check", "Status", "Observed", "Expected"),
                 ((c.name, f"**{c.status.value}**", c.observed, c.expected) for c in checks)))
    failed = [c for c in checks if c.status is Status.FAIL]
    print(f"\n{len(failed)} FAIL, {sum(c.status is Status.WARN for c in checks)} WARN, "
          f"{sum(c.status is Status.UNKNOWN for c in checks)} UNKNOWN.")
    return 1 if failed else 0


def _since(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return Path(value).stat().st_mtime


def _allowed(manifest: str | None) -> frozenset[str]:
    if manifest is None:
        return frozenset()
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    return frozenset(item["sha256"] for item in data.get("recordings", []) if item.get("sha256"))


def cmd_files(args: argparse.Namespace) -> int:
    paths = args.paths or list(DEFAULT_PATHS)
    since = _since(args.since)
    scan = scan_tree(paths, newer_than=since, allowed_sha256=_allowed(args.allow_manifest))
    print("## Audio files on persistent or shared storage\n")
    print("Paths: " + ", ".join(f"`{p}`" for p in paths) + "\n")
    print(f"Files checked: {scan.files_checked}; unreadable entries: {scan.unreadable}"
          + (" (run with sudo for full coverage)" if scan.unreadable else "") + "\n")
    print(_findings_table(scan.findings))
    if since is not None:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(since))
        print(f"\n### Files created or modified since {stamp}\n")
        shown = scan.new_files[: args.max_new]
        print("\n".join(f"- `{p}`" for p in shown) or "None.")
        if len(scan.new_files) > len(shown):
            print(f"- ... and {len(scan.new_files) - len(shown)} more")
    return 1 if scan.findings else 0


def cmd_payloads(args: argparse.Namespace) -> int:
    source = sys.stdin.buffer if args.file in (None, "-") else open(args.file, "rb")
    findings: list[Finding] = []
    count = 0
    print("## Message payloads\n")
    try:
        for number, line in enumerate(source, start=1):
            line = line.rstrip(b"\r\n")
            if not line:
                continue
            count += 1
            location = f"line {number}"
            if args.mqtt:  # `mosquitto_sub -v` prints "<topic> <payload>"
                topic, _, line = line.partition(b" ")
                location = f"{topic.decode('utf-8', 'replace')} (line {number})"
            for finding in inspect_payload(line, location=location):
                findings.append(finding)
                print(f"- FINDING `{finding.location}`: {finding.reason}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        if source is not sys.stdin.buffer:
            source.close()
    print(f"\nPayloads inspected: {count}; findings: {len(findings)}.")
    return 1 if findings else 0


def cmd_control(args: argparse.Namespace) -> int:
    from txori_kantua.messaging import ContractViolation, validate

    directory = Path(args.directory)
    # A neutral extension: the file must be caught by its content, not its name.
    control = directory / f"txori-privacy-control-{secrets.token_hex(4)}.dat"
    results = []
    try:
        control.write_bytes(synthetic_wav())
        scan = scan_tree([directory])
        file_ok = any(f.location == str(control) for f in scan.findings)
        results.append(("Synthetic WAV planted in " + f"`{directory}`", file_ok))
    finally:
        control.unlink(missing_ok=True)
    results.append(("Control file removed by the audit", not control.exists()))

    payload = control_payload()
    payload_ok = bool(inspect_payload(payload))
    results.append(("Base64 audio inside a detection payload", payload_ok))
    try:
        validate("detection", json.loads(payload))
        contract_ok = False
    except ContractViolation:
        contract_ok = True
    results.append(("Detection contract rejects the same payload", contract_ok))

    print("## Control self-test\n")
    print("Synthetic 1 kHz tone generated by the audit; no recorded sound is used.\n")
    print(_table(("Control", "Detected"), ((name, "yes" if ok else "**NO**") for name, ok in results)))
    return 0 if all(ok for _, ok in results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m txori_kantua.privacy.audit",
        description="Audit that no audio reaches disk, messages or logs (issue #11).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    system = sub.add_parser("system", help="swap, core dumps, /tmp and journald")
    system.add_argument("--pid", type=int, help="also check the core limit of this process")
    system.add_argument("--root", default="/", help=argparse.SUPPRESS)
    system.set_defaults(func=cmd_system)

    files = sub.add_parser("files", help="look for audio files")
    files.add_argument("paths", nargs="*", help=f"default: {' '.join(DEFAULT_PATHS)}")
    files.add_argument("--since", help="epoch seconds, or a file whose mtime marks the start")
    files.add_argument("--allow-manifest", help="corpus manifest whose sha256 values are allowed")
    files.add_argument("--max-new", type=int, default=50, help="new files listed (default 50)")
    files.set_defaults(func=cmd_files)

    payloads = sub.add_parser("payloads", help="inspect one payload per line")
    payloads.add_argument("file", nargs="?", help="file with one payload per line; default stdin")
    payloads.add_argument("--mqtt", action="store_true", help="lines are `mosquitto_sub -v` output")
    payloads.set_defaults(func=cmd_payloads)

    control = sub.add_parser("control", help="prove that the audit detects planted audio")
    control.add_argument("directory", help="writable directory to plant the control file in")
    control.set_defaults(func=cmd_control)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
