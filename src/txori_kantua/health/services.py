"""Declared status of each station service, from systemd.

Mapping of systemd states to the contract (``healthy`` / ``degraded`` /
``failed``):

| systemd                                         | contract   |
|-------------------------------------------------|------------|
| active + running (or exited for a oneshot)      | healthy    |
| activating, reloading, deactivating             | degraded   |
| active but restarted since the last check       | degraded   |
| inactive (stopped), failed, unknown unit        | failed     |

A controlled stop (``systemctl stop``) is therefore *not healthy*, which is
acceptance criterion 2 of #24. ``systemctl show`` needs no privileges.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass

PROPERTIES = ("LoadState", "ActiveState", "SubState", "NRestarts")

Runner = Callable[[list[str]], str]


def _systemctl(command: list[str]) -> str:
    out = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    return out.stdout


@dataclass(frozen=True)
class UnitState:
    load: str
    active: str
    sub: str
    restarts: int | None


def parse_show(text: str) -> UnitState:
    fields = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    restarts = fields.get("NRestarts", "")
    return UnitState(
        load=fields.get("LoadState", "unknown"),
        active=fields.get("ActiveState", "unknown"),
        sub=fields.get("SubState", "unknown"),
        restarts=int(restarts) if restarts.isdigit() else None,
    )


def unit_state(unit: str, run: Runner = _systemctl) -> UnitState:
    try:
        text = run(["systemctl", "show", unit, "--property=" + ",".join(PROPERTIES)])
    except (OSError, subprocess.TimeoutExpired):
        return UnitState("unknown", "unknown", "unknown", None)
    return parse_show(text)


def classify(state: UnitState, previous_restarts: int | None = None) -> str:
    if state.load != "loaded":
        return "failed"
    if state.active == "active":
        if state.sub not in ("running", "exited", "listening", "waiting"):
            return "degraded"
        if previous_restarts is not None and state.restarts is not None and state.restarts > previous_restarts:
            return "degraded"
        return "healthy"
    if state.active in ("activating", "reloading", "deactivating"):
        return "degraded"
    return "failed"


class ServiceWatcher:
    """Remembers restart counters so a crash loop shows as ``degraded``."""

    def __init__(self, units: Mapping[str, str], run: Runner = _systemctl) -> None:
        if not units:
            raise ValueError("at least one service to watch")
        self.units = dict(units)
        self._run = run
        self._restarts: dict[str, int | None] = {}
        self.last_states: dict[str, UnitState] = {}

    def check(self) -> dict[str, str]:
        result = {}
        for name, unit in self.units.items():
            state = unit_state(unit, self._run)
            result[name] = classify(state, self._restarts.get(name))
            self._restarts[name] = state.restarts
            self.last_states[name] = state
        return result
