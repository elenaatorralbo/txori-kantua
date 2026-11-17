"""Synthetic checks of evidence tooling; these do not validate physical devices."""
import importlib.util
from pathlib import Path


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'tools' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_capture_held_inputs_do_not_repeat():
    mod = load('check_inputs')
    now = [0.0]
    rows = []
    def sleep(dt):
        now[0] += dt
    mod.capture(lambda: (now[0] >= .1, now[0] >= .1), rows.append,
                warmup_ms=0, debounce_ms=20, duration=.5, interval=.01,
                clock=lambda: now[0], sleep=sleep)
    assert sum(r[5] for r in rows) == 1
    assert sum(r[6] for r in rows) == 1
    assert rows[0][1] == 0
    assert rows[-1][1] > 400


def test_lcd_cleans_up_after_observer_failure():
    mod = load('check_lcd')
    class LCD:
        cleared = False
        def setCursor(self, row, col): pass
        def write(self, text): assert len(text) == 16
        def clear(self): self.cleared = True
    lcd = LCD()
    import pytest
    def fail(prompt): raise RuntimeError('interrupted')
    with pytest.raises(RuntimeError): mod.run(lcd, fail)
    assert lcd.cleared


def test_lcd_cases_include_padded_overwrite_and_ascii():
    cases = list(load('check_lcd').cases())
    assert cases[-1][1] == ('Blue tit        ', '                ')
    assert all(len(row) == 16 and row.isascii() for _, rows in cases for row in rows)
