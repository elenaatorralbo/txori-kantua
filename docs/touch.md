# Touch debounce — desktop implementation

Partial progress for [#5](https://github.com/elenaatorralbo/txori-kantua/issues/5).
`txori_kantua.touch.TouchDebouncer` accepts logical input samples independently
of the sensor model, connection, electrical polarity or GPIO library.

## Behaviour

- Release must be observed consistently for the debounce interval before arming.
- A subsequent press must also stay consistent for that interval to emit an action.
- Holding the input emits no additional actions. Brief release noise cannot rearm it.
- Starting while pressed emits nothing until a stable release and a new press.
- `None` resets pending input and disarms the handler when an adapter reports failure.
- The default interval is 50 ms, configurable and pending measurement on the sensor.

Poll regularly, substantially faster than the configured interval. The algorithm
only knows the supplied samples: it cannot detect transitions between polls or
infer a physically disconnected wire from an ordinary GPIO level. Use integer
milliseconds from `time.monotonic_ns() // 1_000_000`; do not use wall-clock time.

```python
from txori_kantua.touch import TouchDebouncer

touch = TouchDebouncer(debounce_ms=50)
# Synthetic samples, not a hardware measurement:
for now_ms, pressed in [(0, False), (50, False), (100, True), (150, True), (200, True)]:
    if touch.update(pressed, now_ms):
        print("One touch action at", now_ms)  # 150 only
```

Run `python -m pytest tests/test_touch.py` after installing the development
dependencies with `python -m pip install -e ".[dev]"` in a virtual environment.
Tests cover bounce, holds, startup, unavailable input and ten simulated cycles.

## Pending physical work

Confirm model, wiring, active level and stabilisation time; connect an adapter
that supplies logical booleans; tune the interval; record ten real touch cycles,
false triggers and disconnect behaviour. [PIR logic](pir.md) is implemented
separately; physical PIR validation is still pending within #5. Desktop tests
do not satisfy the physical acceptance criteria or close the issue.
