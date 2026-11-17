"""Read-only checks of how process memory could reach persistent storage.

docs/privacy.md requires that a memory page holding audio never reaches disk.
On Linux that can happen through disk-backed swap, zram writeback to a backing
device, or a core dump. These checks read ``/proc``, ``/sys`` and ``/etc``
only; they change nothing and do not need root, although some values (other
users' processes, root-only configuration) may then show as UNKNOWN.

``root`` is injectable so the logic can be tested with a fake tree.
"""

from __future__ import annotations

import configparser
import resource
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    observed: str
    expected: str


def run_checks(root: Path = Path("/"), *, pid: int | None = None) -> list[Check]:
    """Run every check. ``pid`` adds the core limit of a running service."""
    checks = [
        check_swap(root),
        check_core_pattern(root),
        check_suid_dumpable(root),
        check_tmp(root),
        check_journald(root),
        check_stored_coredumps(root),
    ]
    if pid is None:
        checks.append(check_own_core_limit())
    else:
        checks.append(check_process_core_limit(root, pid))
    return checks


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def check_swap(root: Path) -> Check:
    expected = "no disk-backed swap; zram allowed only without a writeback device"
    text = _read(root / "proc/swaps")
    if text is None:
        return Check("Swap", Status.UNKNOWN, "/proc/swaps not readable", expected)
    devices = [line.split() for line in text.splitlines()[1:] if line.strip()]
    if not devices:
        return Check("Swap", Status.PASS, "no active swap", expected)
    problems, notes = [], []
    for fields in devices:
        name, kind = fields[0], fields[1] if len(fields) > 1 else "?"
        if name.startswith("/dev/zram"):
            backing = _read(root / "sys/block" / Path(name).name / "backing_dev")
            backing = (backing or "unknown").strip()
            if backing in ("none", ""):
                notes.append(f"{name} (zram in RAM, no writeback)")
            else:
                problems.append(f"{name} (zram writeback to {backing})")
        else:
            problems.append(f"{name} ({kind} on disk)")
    observed = "; ".join(problems + notes)
    return Check("Swap", Status.FAIL if problems else Status.PASS, observed, expected)


def _coredump_storage(root: Path) -> str | None:
    """Effective ``Storage=`` of systemd-coredump, None if not configured."""
    files = [root / "etc/systemd/coredump.conf"]
    dropins = root / "etc/systemd/coredump.conf.d"
    if dropins.is_dir():
        files += sorted(dropins.glob("*.conf"))
    storage = None
    for path in files:
        text = _read(path)
        if text is None:
            continue
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        try:
            parser.read_string(text)
        except configparser.Error:
            continue
        if parser.has_option("Coredump", "Storage"):
            storage = parser.get("Coredump", "Storage").strip().lower()
    return storage


def check_core_pattern(root: Path) -> Check:
    expected = "dumps disabled: systemd-coredump Storage=none, or core limit 0 for audio processes"
    pattern = _read(root / "proc/sys/kernel/core_pattern")
    if pattern is None:
        return Check("Core dump handler", Status.UNKNOWN, "core_pattern not readable", expected)
    pattern = pattern.strip()
    if pattern.startswith("|") and "systemd-coredump" in pattern:
        storage = _coredump_storage(root) or "external (systemd default)"
        status = Status.PASS if storage == "none" else Status.FAIL
        return Check("Core dump handler", status, f"systemd-coredump, Storage={storage}", expected)
    if pattern.startswith("|"):
        return Check("Core dump handler", Status.WARN, f"pipe to {pattern[1:].split()[0]}: review it", expected)
    # Plain file pattern: safe only if every audio process has a zero core limit,
    # which check_*_core_limit reports separately.
    return Check("Core dump handler", Status.WARN, f"file pattern {pattern!r}; depends on the core limit", expected)


def check_suid_dumpable(root: Path) -> Check:
    expected = "fs.suid_dumpable = 0"
    value = _read(root / "proc/sys/fs/suid_dumpable")
    if value is None:
        return Check("fs.suid_dumpable", Status.UNKNOWN, "not readable", expected)
    value = value.strip()
    return Check("fs.suid_dumpable", Status.PASS if value == "0" else Status.WARN, value, expected)


def check_own_core_limit() -> Check:
    expected = "hard core limit 0 in the audio service (LimitCORE=0)"
    soft, hard = resource.getrlimit(resource.RLIMIT_CORE)
    observed = f"this shell: soft={_limit(soft)} hard={_limit(hard)}; use --pid for the service"
    return Check("Core limit", Status.PASS if hard == 0 else Status.WARN, observed, expected)


def check_process_core_limit(root: Path, pid: int) -> Check:
    expected = "hard core limit 0 in the audio service (LimitCORE=0)"
    text = _read(root / f"proc/{pid}/limits")
    if text is None:
        return Check(f"Core limit of PID {pid}", Status.UNKNOWN, "limits not readable", expected)
    for line in text.splitlines():
        if line.startswith("Max core file size"):
            fields = line.split()
            soft, hard = fields[4], fields[5]
            status = Status.PASS if hard == "0" else Status.FAIL
            return Check(f"Core limit of PID {pid}", status, f"soft={soft} hard={hard}", expected)
    return Check(f"Core limit of PID {pid}", Status.UNKNOWN, "no core line", expected)


def _limit(value: int) -> str:
    return "unlimited" if value == resource.RLIM_INFINITY else str(value)


def _mount_type(root: Path, mountpoint: str) -> str | None:
    text = _read(root / "proc/self/mounts")
    if text is None:
        return None
    found = None
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[1] == mountpoint:
            found = fields[2]  # the last mount on a path wins
    return found


def check_tmp(root: Path) -> Check:
    expected = "/tmp on tmpfs, and PrivateTmp=yes in the audio service"
    kind = _mount_type(root, "/tmp")
    if kind is None:
        return Check("/tmp", Status.WARN, "/tmp is on the root filesystem (disk)", expected)
    return Check("/tmp", Status.PASS if kind == "tmpfs" else Status.WARN, f"mounted as {kind}", expected)


def check_journald(root: Path) -> Check:
    expected = "informational: logs never contain audio, whatever the storage"
    storage = None
    files = [root / "etc/systemd/journald.conf"]
    dropins = root / "etc/systemd/journald.conf.d"
    if dropins.is_dir():
        files += sorted(dropins.glob("*.conf"))
    for path in files:
        text = _read(path)
        if text is None:
            continue
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        try:
            parser.read_string(text)
        except configparser.Error:
            continue
        if parser.has_option("Journal", "Storage"):
            storage = parser.get("Journal", "Storage").strip()
    persistent = (root / "var/log/journal").is_dir()
    observed = f"Storage={storage or 'auto (default)'}; /var/log/journal {'exists' if persistent else 'absent'}"
    return Check("journald", Status.PASS, observed, expected)


def check_stored_coredumps(root: Path) -> Check:
    expected = "no stored core dumps"
    directory = root / "var/lib/systemd/coredump"
    try:
        dumps = [p for p in directory.iterdir() if p.is_file()]
    except FileNotFoundError:
        return Check("Stored core dumps", Status.PASS, "directory absent", expected)
    except OSError:
        return Check("Stored core dumps", Status.UNKNOWN, "directory not readable (run with sudo)", expected)
    status = Status.PASS if not dumps else Status.FAIL
    return Check("Stored core dumps", status, f"{len(dumps)} file(s) in {directory}", expected)
