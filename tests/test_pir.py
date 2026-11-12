"""Synthetic PIR sequences, not evidence of physical sensor operation."""

import pytest

from txori_kantua.pir import PresenceReading, PresenceState as State, PresenceTracker


def test_warmup_ignores_changes_until_exact_boundary():
    pir = PresenceTracker(stabilization_ms=100)
    assert pir.update(True, 1000) == PresenceReading(State.STABILIZING)
    assert pir.update(False, 1050) == PresenceReading(State.STABILIZING)
    assert pir.update(True, 1099) == PresenceReading(State.STABILIZING)
    assert pir.update(True, 1100) == PresenceReading(State.PRESENT, True)


def test_held_presence_activates_once_and_absence_rearms():
    pir = PresenceTracker(stabilization_ms=0)
    assert pir.update(False, 0) == PresenceReading(State.ABSENT)
    assert pir.update(True, 1).activated
    assert pir.update(True, 1) == PresenceReading(State.PRESENT)
    assert pir.update(True, 10000) == PresenceReading(State.PRESENT)
    assert pir.update(False, 10001) == PresenceReading(State.ABSENT)
    assert pir.update(True, 10002).activated


def test_unavailable_is_not_absence_and_restarts_warmup():
    pir = PresenceTracker(stabilization_ms=100)
    pir.update(False, 0)
    assert pir.update(True, 100).activated
    assert pir.update(None, 110) == PresenceReading(State.UNAVAILABLE)
    assert pir.update(None, 500) == PresenceReading(State.UNAVAILABLE)
    assert pir.update(True, 600) == PresenceReading(State.STABILIZING)
    assert pir.update(True, 699) == PresenceReading(State.STABILIZING)
    assert pir.update(True, 700) == PresenceReading(State.PRESENT, True)


def test_ten_simulated_cycles():
    pir = PresenceTracker(stabilization_ms=0)
    events = []
    for index in range(10):
        assert pir.update(False, index * 3).state == State.ABSENT
        events.append(pir.update(True, index * 3 + 1).activated)
        assert not pir.update(True, index * 3 + 2).activated
    assert events == [True] * 10


@pytest.mark.parametrize("interval", [-1, True, 0.5])
def test_invalid_stabilization(interval):
    with pytest.raises(ValueError):
        PresenceTracker(stabilization_ms=interval)


@pytest.mark.parametrize("time", [-1, True, 0.5])
def test_invalid_clock(time):
    with pytest.raises(ValueError):
        PresenceTracker(stabilization_ms=0).update(False, time)


def test_backwards_time_rejected_without_changing_presence():
    pir = PresenceTracker(stabilization_ms=0)
    assert pir.update(True, 10).activated
    with pytest.raises(ValueError):
        pir.update(False, 9)
    assert not pir.update(True, 11).activated


def test_requires_logical_boolean():
    with pytest.raises(TypeError):
        PresenceTracker(stabilization_ms=0).update(1, 0)
