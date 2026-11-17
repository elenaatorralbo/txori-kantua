# Environmental sensors validation — absent-sensors

- **Date (UTC):** 2026-11-17T16:54:28Z
- **Run by:** Erik Eguskiza (eeguskiza), over SSH
- **Reviewed by:** _fill in_
- **Issue / PR:** #4 / #51
- **Commit:** ed5a5c2
- **Hardware:** Raspberry Pi 5 Model B Rev 1.0; Debian GNU/Linux 13 (trixie); aarch64
- **Relevant versions:** Python 3.13.5; kernel 6.18.60+rpt-rpi-2712; arecord: version 1.2.14 by Jaroslav Kysela <perex@perex.cz>
- **Procedure:** `PYTHONPATH=src python3 -m txori_kantua.environment.env_check --samples 5 --dht-pin 16 --bme280-address 0x77 --light-channel 2 --phase absent-sensors`

## Setup

- Rounds per phase: 5, every 2 s; phases: `absent-sensors`
- DHT11 on GPIO 16 (BCM), driver `txori_kantua.dht11` (lgpio)
- BME280 on I2C bus 1, **not found** (probed 0x77); forced mode, oversampling x1, filter off
- Grove light sensor on analogue port A2: Grove Base Hat for Raspberry Pi. Value in **raw** per mille of the supply (0..1000), not lux

## Summary

| Phase | Channel | ok | unavailable | error | Min | Mean | Max | Std dev | First failure |
|---|---|---|---|---|---|---|---|---|---|
| absent-sensors | `dht11.temperature` (degC) | 0 | 5 | 0 |  | | |  | DHT11: only 0 pulses received |
| absent-sensors | `dht11.humidity` (percent) | 0 | 5 | 0 |  | | |  | DHT11: only 0 pulses received |
| absent-sensors | `bme280.pressure` (hPa) | 0 | 5 | 0 |  | | |  | no BME280 found: BME280 at 0x77 does not answer: [Errno 121] Remote I/O error |
| absent-sensors | `bme280.temperature` (degC) | 0 | 5 | 0 |  | | |  | no BME280 found: BME280 at 0x77 does not answer: [Errno 121] Remote I/O error |
| absent-sensors | `bme280.humidity` (percent) | 0 | 5 | 0 |  | | |  | no BME280 found: BME280 at 0x77 does not answer: [Errno 121] Remote I/O error |
| absent-sensors | `light.raw` (raw) | 5 | 0 | 0 | 647.00 | 652.20 | 654.00 | 2.950 |  |
| absent-sensors | `light.millivolts` (mV) | 5 | 0 | 0 | 2155.00 | 2182.20 | 2192.00 | 15.369 |  |

## Readings — absent-sensors

| # | UTC | t (s) | `dht11.temperature` | `dht11.humidity` | `bme280.pressure` | `bme280.temperature` | `bme280.humidity` | `light.raw` | `light.millivolts` |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-17T16:54:20.644Z | 0.0 | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | 647.00 | 2155.00 |
| 2 | 2026-11-17T16:54:22.644Z | 2.0 | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | 653.00 | 2192.00 |
| 3 | 2026-11-17T16:54:24.644Z | 4.0 | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | 654.00 | 2188.00 |
| 4 | 2026-11-17T16:54:26.645Z | 6.0 | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | 653.00 | 2190.00 |
| 5 | 2026-11-17T16:54:28.644Z | 8.0 | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | _unavailable_ | 654.00 | 2186.00 |

## Result

| Check | Result |
|---|---|
| `dht11.temperature`: at least 30 dated valid readings (0) | **FAIL** |
| `dht11.humidity`: at least 30 dated valid readings (0) | **FAIL** |
| `bme280.pressure`: at least 30 dated valid readings (0) | **FAIL** |
| `light.raw`: at least 30 dated valid readings (5) | **FAIL** |
| Every failed read recorded as empty with explicit quality (25 failed reads) | PASS |

## To fill in by hand

- Setup: each channel pointed at a place with **no sensor**, without touching the wiring:
  DHT11 driver on GPIO 16 (Grove D16, empty), BME280 probed only at 0x77 (the
  module answers at 0x76; nothing at 0x77), light read from analogue port A2 (empty).
  The real sensors stay on GPIO 5, 0x76 and A0. `txori-kantua.service` stopped.
- This is the "sensor absent at start-up" case. Unplugging a sensor while it
  runs was not done: nobody was at the Pi. The fake-bus tests cover the
  unplug/replug sequence (`tests/environment/test_sensors.py`).
- Observations and limitations:
  - DHT11 and BME280: every read is `unavailable` with its cause
    ("only 0 pulses received", I2C `Remote I/O error`), the value is empty,
    and no 0 is recorded. The *Result* check on failed reads passes.
  - **Light: an empty analogue port reads about 650/1000 (2.19 V), not 0.**
    The floating input looks like a plausible light level. Absence of the
    analogue light sensor **cannot be detected** in software. This confirms the
    limitation in `docs/environment-sensors.md`. Mitigation for #14: check
    the light channel in the start-up procedure (cover it and see the value drop).
  - The run exits 1 because 5 rounds are below the 30-reading check; that check
    belongs to the baseline report.
