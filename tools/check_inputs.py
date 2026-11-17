"""Physical GPIO sampling for #5; stdout is timestamped CSV, never a pass claim."""
import argparse
import csv
from datetime import datetime, timezone
import sys
import time

from txori_kantua.pir import PresenceTracker
from txori_kantua.touch import TouchDebouncer


def capture(read, emit, *, warmup_ms, debounce_ms, duration, interval,
            clock=time.monotonic, sleep=time.sleep):
    pir = PresenceTracker(stabilization_ms=warmup_ms)
    touch = TouchDebouncer(debounce_ms)
    start = clock()
    while (elapsed := clock() - start) < duration:
        raw_pir, raw_touch = read()
        now_ms = int(elapsed * 1000)
        state = pir.update(raw_pir, now_ms)
        action = touch.update(raw_touch, now_ms)
        emit([datetime.now(timezone.utc).isoformat(), now_ms,
              int(raw_pir), int(raw_touch), state.state.value,
              int(state.activated), int(action)])
        sleep(interval)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--chip', type=int, required=True)
    p.add_argument('--pir-pin', type=int, required=True, help='BCM GPIO offset, not header pin')
    p.add_argument('--touch-pin', type=int, required=True)
    p.add_argument('--pir-active', type=int, choices=(0, 1), required=True)
    p.add_argument('--touch-active', type=int, choices=(0, 1), required=True)
    p.add_argument('--warmup-ms', type=int, required=True)
    p.add_argument('--debounce-ms', type=int, required=True)
    p.add_argument('--seconds', type=float, default=300)
    p.add_argument('--interval-ms', type=int, default=5)
    a = p.parse_args()
    if (a.pir_pin == a.touch_pin or min(a.chip, a.pir_pin, a.touch_pin, a.warmup_ms) < 0
            or a.debounce_ms <= 0 or a.seconds <= 0 or a.interval_ms <= 0):
        p.error('Use distinct nonnegative GPIOs, nonnegative warmup and positive timing values')
    import lgpio
    handle = lgpio.gpiochip_open(a.chip)
    try:
        # No output drive or assumed pull configuration.
        lgpio.gpio_claim_input(handle, a.pir_pin)
        lgpio.gpio_claim_input(handle, a.touch_pin)
        writer = csv.writer(sys.stdout)
        writer.writerow(['utc', 'elapsed_ms', 'pir_active', 'touch_active',
                         'pir_state', 'pir_action', 'touch_action'])
        def emit(row):
            writer.writerow(row)
            sys.stdout.flush()
        capture(lambda: (lgpio.gpio_read(handle, a.pir_pin) == a.pir_active,
                         lgpio.gpio_read(handle, a.touch_pin) == a.touch_active),
                emit, warmup_ms=a.warmup_ms, debounce_ms=a.debounce_ms,
                duration=a.seconds, interval=a.interval_ms / 1000)
    finally:
        lgpio.gpiochip_close(handle)


if __name__ == '__main__':
    main()
