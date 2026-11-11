"""Synthetic input traces; no claims about the physical touch sensor."""

import pytest

from txori_kantua.touch import TouchDebouncer


def actions(samples, debounce_ms=50):
    touch = TouchDebouncer(debounce_ms)
    return [time for time, state in samples if touch.update(state, time)]


def test_bouncing_press_and_hold_emit_one_action():
    assert actions([
        (0, False), (50, False), (100, True), (110, False),
        (120, True), (169, True), (170, True), (500, True),
    ]) == [170]


def test_brief_release_cannot_rearm():
    assert actions([
        (0, False), (50, False), (100, True), (150, True),
        (200, False), (249, False), (250, True), (300, True),
        (350, False), (400, False), (450, True), (500, True),
    ]) == [150, 500]


def test_short_noise_pulse_is_ignored():
    assert actions([(0, False), (50, False), (100, True), (120, False), (170, False)]) == []


def test_starting_held_requires_release_before_first_action():
    assert actions([
        (0, True), (100, True), (200, False), (250, False),
        (300, True), (350, True),
    ]) == [350]


def test_missing_input_resets_pending_press_and_requires_release():
    assert actions([
        (0, False), (50, False), (100, True), (120, None),
        (200, True), (300, True), (400, False), (450, False),
        (500, True), (550, True),
    ]) == [550]


def test_ten_press_release_cycles_produce_ten_actions():
    samples = []
    for cycle in range(10):
        start = cycle * 200
        samples.extend([(start, False), (start + 50, False),
                        (start + 100, True), (start + 150, True)])
    assert actions(samples) == list(range(150, 2000, 200))


def test_configurable_threshold_and_duplicate_timestamp():
    assert actions([(0, False), (20, False), (30, True), (49, True),
                    (50, True), (50, True)], debounce_ms=20) == [50]


@pytest.mark.parametrize("interval", [0, -1, 1.5, True])
def test_invalid_interval(interval):
    with pytest.raises(ValueError):
        TouchDebouncer(interval)


@pytest.mark.parametrize("time", [-1, 0.5, True])
def test_invalid_time(time):
    with pytest.raises(ValueError):
        TouchDebouncer().update(False, time)


def test_backwards_time_does_not_mutate_state():
    touch = TouchDebouncer()
    touch.update(False, 100)
    with pytest.raises(ValueError):
        touch.update(True, 99)
    touch.update(False, 150)
    touch.update(True, 200)
    assert touch.update(True, 250)


def test_adapter_must_supply_logical_boolean():
    with pytest.raises(TypeError):
        TouchDebouncer().update(1, 0)
