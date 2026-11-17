"""Resource metrics from ``/proc`` and ``/sys``, without third-party packages.

Every reader returns ``None`` when the value cannot be obtained (missing file,
unexpected format), which is what the health contract expects: an unknown
metric is ``null``, never 0.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PROC = Path("/proc")
#: SoC sensor of the Raspberry Pi 5 (cpu-thermal zone).
THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")


@dataclass(frozen=True)
class CpuTimes:
    busy: int
    total: int


def read_cpu_times(proc: Path = PROC) -> CpuTimes | None:
    """Aggregate jiffies of the ``cpu`` line of ``/proc/stat``."""
    try:
        first = (proc / "stat").read_text().splitlines()[0].split()
        if first[0] != "cpu":
            return None
        values = [int(v) for v in first[1:]]
    except (OSError, IndexError, ValueError):
        return None
    # user nice system idle iowait irq softirq steal [guest guest_nice]
    # guest time is already counted in user/nice, so only the first 8 add up.
    fields = values[:8]
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    total = sum(fields)
    return CpuTimes(busy=total - idle, total=total)


def cpu_percent(before: CpuTimes | None, after: CpuTimes | None) -> float | None:
    """Average usage of the whole device between two samples."""
    if before is None or after is None:
        return None
    total = after.total - before.total
    if total <= 0:
        return None
    return round(min(100.0, max(0.0, 100.0 * (after.busy - before.busy) / total)), 1)


def memory_used_bytes(proc: Path = PROC) -> int | None:
    """``MemTotal - MemAvailable``: memory not reclaimable by the kernel."""
    try:
        fields = {}
        for line in (proc / "meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            fields[key] = int(rest.split()[0]) * 1024
        return max(0, fields["MemTotal"] - fields["MemAvailable"])
    except (OSError, KeyError, ValueError, IndexError):
        return None


def cpu_temperature_c(path: Path = THERMAL_ZONE) -> float | None:
    try:
        value = int(path.read_text().strip()) / 1000.0
    except (OSError, ValueError):
        return None
    # Contract range; outside it the sensor is faulty, not the SoC on fire.
    return round(value, 1) if -40.0 <= value <= 150.0 else None


def disk_free_bytes(path: str | Path = "/", statvfs: Callable[[str], os.statvfs_result] = os.statvfs) -> int | None:
    """Space available to unprivileged processes on the volume of ``path``."""
    try:
        st = statvfs(str(path))
    except OSError:
        return None
    return st.f_bavail * st.f_frsize


def uptime_seconds(proc: Path = PROC) -> int | None:
    try:
        return int(float((proc / "uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        return None
