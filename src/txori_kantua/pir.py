"""Logical PIR input tracking without assumptions about wiring or polarity."""

from dataclasses import dataclass
from enum import Enum


class PresenceState(str, Enum):
    UNAVAILABLE = "unavailable"
    STABILIZING = "stabilizing"
    ABSENT = "absent"
    PRESENT = "present"


@dataclass(frozen=True)
class PresenceReading:
    state: PresenceState
    activated: bool = False


class PresenceTracker:
    """Track logical presence and emit one activation per presence interval.

    The caller must choose stabilization_ms from the actual sensor's needs.
    Time starts at the first available sample, and restarts after an unavailable
    sample. A positive sample when stabilization ends emits an activation.
    """

    def __init__(self, *, stabilization_ms: int) -> None:
        if type(stabilization_ms) is not int or stabilization_ms < 0:
            raise ValueError("stabilization_ms must be a non-negative integer")
        self.stabilization_ms = stabilization_ms
        self._started_ms: int | None = None
        self._last_ms: int | None = None
        self._state = PresenceState.UNAVAILABLE

    def update(self, present: bool | None, now_ms: int) -> PresenceReading:
        """Consume a logical sample and monotonic integer milliseconds.

        None is an explicit adapter failure, not an inferred electrical state.
        There is no timer thread: transitions happen only when samples arrive.
        """
        if present is not None and type(present) is not bool:
            raise TypeError("present must be bool or None")
        if type(now_ms) is not int or now_ms < 0:
            raise ValueError("now_ms must be a non-negative integer")
        if self._last_ms is not None and now_ms < self._last_ms:
            raise ValueError("now_ms must not go backwards")
        self._last_ms = now_ms
        if present is None:
            self._started_ms = None
            self._state = PresenceState.UNAVAILABLE
            return PresenceReading(self._state)
        if self._started_ms is None:
            self._started_ms = now_ms
        if now_ms - self._started_ms < self.stabilization_ms:
            self._state = PresenceState.STABILIZING
            return PresenceReading(self._state)
        next_state = PresenceState.PRESENT if present else PresenceState.ABSENT
        activated = present and self._state != PresenceState.PRESENT
        self._state = next_state
        return PresenceReading(self._state, activated)
