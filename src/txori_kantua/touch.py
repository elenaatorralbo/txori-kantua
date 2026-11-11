"""Polling-based touch debounce independent of GPIO polarity and hardware."""

from __future__ import annotations


class TouchDebouncer:
    """Emit one action per stable press, after a stable release.

    Call ``update`` regularly with logical pressed/released samples and integer
    milliseconds from a monotonic clock. The 50 ms default is provisional,
    not a measured property of the real sensor. A missing sample (None) resets
    the state; reconnecting or starting while held cannot create an action.
    """

    def __init__(self, debounce_ms: int = 50) -> None:
        if type(debounce_ms) is not int or debounce_ms <= 0:
            raise ValueError("debounce_ms must be a positive integer")
        self.debounce_ms = debounce_ms
        self._last_ms: int | None = None
        self._candidate: bool | None = None
        self._since_ms = 0
        self._armed = False

    def update(self, pressed: bool | None, now_ms: int) -> bool:
        """Return True only when a new stable press should trigger an action.

        A candidate must remain unchanged in the observed samples for at least
        ``debounce_ms``. Repeated equal timestamps are allowed; backwards time
        is rejected. None means the adapter detected an unavailable input, not
        that a disconnected wire can automatically be recognised in software.
        """
        if pressed is not None and type(pressed) is not bool:
            raise TypeError("pressed must be bool or None")
        if type(now_ms) is not int or now_ms < 0:
            raise ValueError("now_ms must be a non-negative integer")
        if self._last_ms is not None and now_ms < self._last_ms:
            raise ValueError("now_ms must not go backwards")
        self._last_ms = now_ms

        if pressed is None:
            self._candidate = None
            self._armed = False
            return False
        if pressed is not self._candidate:
            self._candidate = pressed
            self._since_ms = now_ms
            return False
        if now_ms - self._since_ms < self.debounce_ms:
            return False
        if not pressed:
            self._armed = True
            return False
        if self._armed:
            self._armed = False
            return True
        return False
