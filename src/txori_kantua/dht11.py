"""
dht11.py - minimal DHT11 driver for the Raspberry Pi 5 (lgpio edge alerts)

The DHT11 talks a one-wire protocol with pulses of tens of microseconds.
Instead of polling the pin from Python, the kernel timestamps every edge and
the high pulses are decoded afterwards: ~27 us means 0, ~70 us means 1.
"""
import threading
import time

import lgpio

CHIP = 0
MIN_INTERVAL_S = 1.0


class DHT11:
    def __init__(self, pin, chip=CHIP):
        self.pin = pin
        self.handle = lgpio.gpiochip_open(chip)
        self.lock = threading.Lock()
        self.edges = []
        self.last_time = 0.0
        lgpio.gpio_claim_input(self.handle, pin, lgpio.SET_PULL_UP)

    def _on_edge(self, _chip, _gpio, level, tick):
        self.edges.append((level, tick))

    def _transfer(self):
        self.edges = []
        lgpio.gpio_claim_output(self.handle, self.pin, 0)
        time.sleep(0.02)
        lgpio.gpio_claim_alert(self.handle, self.pin, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP)
        cb = lgpio.callback(self.handle, self.pin, lgpio.BOTH_EDGES, self._on_edge)
        time.sleep(0.03)
        cb.cancel()
        lgpio.gpio_free(self.handle, self.pin)
        lgpio.gpio_claim_input(self.handle, self.pin, lgpio.SET_PULL_UP)
        highs = [(t1 - t0) / 1000 for (l0, t0), (l1, t1) in zip(self.edges, self.edges[1:])
                 if l0 == 1 and l1 == 0]
        if len(highs) < 40:
            raise RuntimeError(f"DHT11: only {len(highs)} pulses received")
        bits = [1 if us > 50 else 0 for us in highs[-40:]]
        data = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, 40, 8)]
        if (sum(data[:4]) & 0xFF) != data[4]:
            raise RuntimeError(f"DHT11: bad checksum {data}")
        return {"humidity": data[0] + data[1] / 10, "temperature": data[2] + (data[3] & 0x7F) / 10}

    def read(self):
        with self.lock:
            time.sleep(max(0.0, self.last_time + MIN_INTERVAL_S - time.monotonic()))
            try:
                return self._transfer()
            finally:
                self.last_time = time.monotonic()

    def close(self):
        lgpio.gpiochip_close(self.handle)
