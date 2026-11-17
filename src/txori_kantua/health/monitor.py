"""Health monitor: one contract ``health`` event per interval (issue #24).

    python -m txori_kantua.health.monitor --once
    python -m txori_kantua.health.monitor --interval 30 --service station=txori-kantua.service

Each event is validated against ``contracts/mqtt/health.schema.json`` and
written as one JSON line to stdout, ready for the MQTT publisher of #18
(topic ``txori/v1/{station_id}/health``, QoS 1, retained). Until that
publisher exists, stdout is the output; under systemd it reaches journald.

Logs go to stderr as JSON lines with the ``event_id`` of each event, so a log
line and a stored event can be matched. A warning is logged when a measured
budget is exceeded (thresholds below) or a service stops being healthy.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from txori_kantua.messaging import new_health

from . import jsonlog, metrics
from .services import ServiceWatcher

LOG = logging.getLogger("txori_kantua.health")

#: Services of the station that exist today. Others are added as they are deployed.
DEFAULT_SERVICES = {"station": "txori-kantua.service"}


@dataclass(frozen=True)
class Thresholds:
    """Budgets from ADR 0001 (#8) and degraded mode (#26). Adjust after the Pi measurements."""

    cpu_temperature_c: float = 80.0      # ADR 0001: <= 80 degC with no throttling
    memory_used_bytes: int = 3 * 1024**3  # leaves >= 1 GiB of a 4 GiB Pi 5 free
    disk_free_bytes: int = 1 * 1024**3    # below this, degraded mode (ADR 0007, #26)
    cpu_percent: float = 90.0


def breaches(event: Mapping[str, object], limits: Thresholds) -> list[str]:
    found = []
    temp = event.get("cpu_temperature_c")
    if isinstance(temp, (int, float)) and temp >= limits.cpu_temperature_c:
        found.append(f"cpu_temperature_c {temp} >= {limits.cpu_temperature_c}")
    used = event.get("memory_used_bytes")
    if isinstance(used, int) and used >= limits.memory_used_bytes:
        found.append(f"memory_used_bytes {used} >= {limits.memory_used_bytes}")
    free = event.get("disk_free_bytes")
    if isinstance(free, int) and free <= limits.disk_free_bytes:
        found.append(f"disk_free_bytes {free} <= {limits.disk_free_bytes}")
    cpu = event.get("cpu_percent")
    if isinstance(cpu, (int, float)) and cpu >= limits.cpu_percent:
        found.append(f"cpu_percent {cpu} >= {limits.cpu_percent}")
    return found


class Monitor:
    def __init__(self, station_id: str, watcher: ServiceWatcher, *, disk_path: str = "/",
                 proc: Path = metrics.PROC, thermal: Path = metrics.THERMAL_ZONE,
                 limits: Thresholds = Thresholds()) -> None:
        self.station_id = station_id
        self.watcher = watcher
        self.disk_path = disk_path
        self.proc = proc
        self.thermal = thermal
        self.limits = limits
        self._cpu = metrics.read_cpu_times(proc)
        self._previous_services: dict[str, str] = {}

    def sample(self) -> dict:
        cpu_now = metrics.read_cpu_times(self.proc)
        services = self.watcher.check()
        event = new_health(
            station_id=self.station_id,
            services=services,
            cpu_percent=metrics.cpu_percent(self._cpu, cpu_now),
            memory_used_bytes=metrics.memory_used_bytes(self.proc),
            cpu_temperature_c=metrics.cpu_temperature_c(self.thermal),
            disk_free_bytes=metrics.disk_free_bytes(self.disk_path),
            uptime_seconds=metrics.uptime_seconds(self.proc),
        )
        self._cpu = cpu_now
        self._log(event)
        return event

    def _log(self, event: dict) -> None:
        event_id = event["event_id"]
        for name, status in event["services"].items():
            before = self._previous_services.get(name)
            if status != before:
                level = logging.INFO if status == "healthy" else logging.WARNING
                state = self.watcher.last_states.get(name)
                LOG.log(level, "service %s is %s", name, status, extra={
                    "event_id": event_id, "service": name, "status": status, "previous": before,
                    "systemd": f"{state.active}/{state.sub}" if state else None})
        self._previous_services = dict(event["services"])
        for breach in breaches(event, self.limits):
            LOG.warning("budget exceeded: %s", breach, extra={"event_id": event_id})


def parse_services(values: Sequence[str] | None) -> dict[str, str]:
    if not values:
        return dict(DEFAULT_SERVICES)
    services = {}
    for value in values:
        name, sep, unit = value.partition("=")
        if not sep or not name or not unit:
            raise argparse.ArgumentTypeError(f"--service expects name=unit, got {value!r}")
        services[name] = unit
    return services


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m txori_kantua.health.monitor",
                                description="Publish station health events (issue #24).")
    p.add_argument("--station-id", default="station-01")
    p.add_argument("--service", action="append", help="name=systemd unit; repeat (default: station=txori-kantua.service)")
    p.add_argument("--interval", type=float, default=30.0, help="seconds between events (CPU is averaged over it)")
    p.add_argument("--disk-path", default="/", help="volume whose free space is reported (where the database lives)")
    p.add_argument("--once", action="store_true", help="emit a single event and exit")
    return p


def main(argv: Sequence[str] | None = None, *, watcher_factory: Callable[[dict[str, str]], ServiceWatcher] = ServiceWatcher,
         out=None, stop: threading.Event | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interval < 1:
        print("--interval must be >= 1 s", file=sys.stderr)
        return 2
    jsonlog.configure()
    out = out or sys.stdout
    stop = stop or threading.Event()
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
    monitor = Monitor(args.station_id, watcher_factory(parse_services(args.service)), disk_path=args.disk_path)
    if args.once:
        # CPU needs two samples: wait one second so the first value is not null.
        time.sleep(1.0)
    while True:
        event = monitor.sample()
        out.write(json.dumps(event, separators=(",", ":")) + "\n")
        out.flush()
        if args.once or stop.wait(args.interval):
            return 0


if __name__ == "__main__":
    sys.exit(main())
