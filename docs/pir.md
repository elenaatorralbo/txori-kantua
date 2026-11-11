# PIR presence — desktop implementation

Partial progress for [#5](https://github.com/elenaatorralbo/txori-kantua/issues/5),
alongside [touch debounce](touch.md). No wiring or hardware driver is assumed.

`PresenceTracker(stabilization_ms=...)` requires an explicit warmup duration:
the real value must be chosen from the identified sensor and validated on the
Pi. Time starts at the first available sample, not at object construction.

Call `update(present, now_ms)` regularly with a logical boolean from the adapter
and `time.monotonic_ns() // 1_000_000`. Results distinguish `stabilizing`,
`absent`, `present` and `unavailable`. Signals during warmup produce no actions.
A positive sample after warmup activates once; sustained presence does not
repeat the action. An absent sample allows a later presence to activate again.

Pass `None` only when the adapter detects unavailable input. This resets warmup;
reconnection must stabilize again. A disconnected wire cannot automatically be
detected from an ordinary GPIO value. The tracker does not invent an absence
timeout, filter false triggers or infer movement between samples. Those policies
need the real sensor's behaviour. LCD timing belongs to #22.

```python
from txori_kantua.pir import PresenceTracker

pir = PresenceTracker(stabilization_ms=100)  # Synthetic example only.
for now_ms, present in [(0, True), (100, False), (200, True), (300, True)]:
    reading = pir.update(present, now_ms)
    print(now_ms, reading.state.value, reading.activated)
# stabilizing/False, absent/False, present/True, present/False
```

Run `python -m pytest tests/test_pir.py tests/test_touch.py` in the development
environment. Synthetic tests cover startup, sustained presence, reconnection,
clock validation and ten cycles. Physical #5 evidence remains pending: model,
electrical levels/polarity, warmup measurement, ten timestamped cycles per input,
false triggers and disconnect behaviour. These tests do not close #5.
