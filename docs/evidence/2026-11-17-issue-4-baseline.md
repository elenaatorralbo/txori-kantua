# Environmental sensors validation

- **Date (UTC):** 2026-11-17T16:47:17Z
- **Run by:** Erik Eguskiza (eeguskiza), over SSH
- **Reviewed by:** _fill in_
- **Issue / PR:** #4 / #51
- **Commit:** c6b6229
- **Hardware:** Raspberry Pi 5 Model B Rev 1.0; Debian GNU/Linux 13 (trixie); aarch64
- **Relevant versions:** Python 3.13.5; kernel 6.18.60+rpt-rpi-2712; arecord: version 1.2.14 by Jaroslav Kysela <perex@perex.cz>
- **Procedure:** `PYTHONPATH=src python3 -m txori_kantua.environment.env_check` from a checkout of the PR branch, with `txori-kantua.service` stopped ([procedure](../environment-sensors.md), step 1)

## Setup

- Rounds per phase: 30, every 2 s; phases: `baseline`
- DHT11 on GPIO 5 (BCM), driver `txori_kantua.dht11` (lgpio)
- BME280 on I2C bus 1, found at `0x76` (probed 0x76, 0x77); forced mode, oversampling x1, filter off
- Grove light sensor on analogue port A0: Grove Base Hat for Raspberry Pi. Value in **raw** per mille of the supply (0..1000), not lux

## Summary

| Phase | Channel | ok | unavailable | error | Min | Mean | Max | Std dev | First failure |
|---|---|---|---|---|---|---|---|---|---|
| baseline | `dht11.temperature` (degC) | 30 | 0 | 0 | 26.40 | 30.58 | 31.20 | 0.845 |  |
| baseline | `dht11.humidity` (percent) | 30 | 0 | 0 | 46.00 | 47.50 | 54.00 | 1.456 |  |
| baseline | `bme280.pressure` (hPa) | 30 | 0 | 0 | 1002.75 | 1002.80 | 1002.87 | 0.031 |  |
| baseline | `bme280.temperature` (degC) | 30 | 0 | 0 | 26.19 | 26.57 | 26.97 | 0.240 |  |
| baseline | `bme280.humidity` (percent) | 30 | 0 | 0 | 45.66 | 46.44 | 47.28 | 0.483 |  |
| baseline | `light.raw` (raw) | 30 | 0 | 0 | 699.00 | 699.20 | 700.00 | 0.407 |  |
| baseline | `light.millivolts` (mV) | 30 | 0 | 0 | 2307.00 | 2308.57 | 2311.00 | 1.006 |  |

## Readings — baseline

| # | UTC | t (s) | `dht11.temperature` | `dht11.humidity` | `bme280.pressure` | `bme280.temperature` | `bme280.humidity` | `light.raw` | `light.millivolts` |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-17T16:46:18.952Z | 0.0 | 26.40 | 54.00 | 1002.87 | 26.97 | 45.66 | 699.00 | 2309.00 |
| 2 | 2026-11-17T16:46:20.952Z | 2.0 | 30.20 | 49.00 | 1002.78 | 26.93 | 45.72 | 699.00 | 2308.00 |
| 3 | 2026-11-17T16:46:22.952Z | 4.0 | 30.30 | 48.00 | 1002.77 | 26.91 | 45.79 | 699.00 | 2307.00 |
| 4 | 2026-11-17T16:46:24.952Z | 6.0 | 30.30 | 48.00 | 1002.80 | 26.87 | 45.83 | 699.00 | 2309.00 |
| 5 | 2026-11-17T16:46:26.952Z | 8.0 | 30.30 | 48.00 | 1002.76 | 26.86 | 45.89 | 700.00 | 2309.00 |
| 6 | 2026-11-17T16:46:28.952Z | 10.0 | 30.30 | 48.00 | 1002.82 | 26.83 | 45.92 | 699.00 | 2309.00 |
| 7 | 2026-11-17T16:46:30.952Z | 12.0 | 30.40 | 48.00 | 1002.78 | 26.79 | 45.95 | 699.00 | 2308.00 |
| 8 | 2026-11-17T16:46:32.952Z | 14.0 | 30.50 | 48.00 | 1002.79 | 26.77 | 46.04 | 699.00 | 2307.00 |
| 9 | 2026-11-17T16:46:34.952Z | 16.0 | 30.50 | 48.00 | 1002.78 | 26.74 | 46.06 | 699.00 | 2307.00 |
| 10 | 2026-11-17T16:46:36.952Z | 18.0 | 30.50 | 48.00 | 1002.85 | 26.71 | 46.12 | 700.00 | 2308.00 |
| 11 | 2026-11-17T16:46:38.952Z | 20.0 | 30.60 | 48.00 | 1002.86 | 26.70 | 46.19 | 700.00 | 2309.00 |
| 12 | 2026-11-17T16:46:40.952Z | 22.0 | 30.60 | 48.00 | 1002.75 | 26.67 | 46.25 | 699.00 | 2308.00 |
| 13 | 2026-11-17T16:46:42.952Z | 24.0 | 30.60 | 48.00 | 1002.80 | 26.63 | 46.30 | 699.00 | 2309.00 |
| 14 | 2026-11-17T16:46:44.952Z | 26.0 | 30.70 | 47.00 | 1002.80 | 26.58 | 46.39 | 699.00 | 2308.00 |
| 15 | 2026-11-17T16:46:46.952Z | 28.0 | 30.70 | 47.00 | 1002.83 | 26.57 | 46.44 | 699.00 | 2310.00 |
| 16 | 2026-11-17T16:46:48.952Z | 30.0 | 30.70 | 47.00 | 1002.80 | 26.55 | 46.48 | 700.00 | 2311.00 |
| 17 | 2026-11-17T16:46:50.952Z | 32.0 | 30.80 | 47.00 | 1002.80 | 26.53 | 46.51 | 700.00 | 2308.00 |
| 18 | 2026-11-17T16:46:52.952Z | 34.0 | 30.80 | 47.00 | 1002.79 | 26.51 | 46.55 | 699.00 | 2308.00 |
| 19 | 2026-11-17T16:46:54.952Z | 36.0 | 30.80 | 47.00 | 1002.82 | 26.48 | 46.59 | 699.00 | 2309.00 |
| 20 | 2026-11-17T16:46:56.952Z | 38.0 | 30.90 | 47.00 | 1002.83 | 26.44 | 46.69 | 700.00 | 2309.00 |
| 21 | 2026-11-17T16:46:58.952Z | 40.0 | 30.90 | 47.00 | 1002.85 | 26.42 | 46.73 | 699.00 | 2309.00 |
| 22 | 2026-11-17T16:47:00.952Z | 42.0 | 30.90 | 47.00 | 1002.78 | 26.38 | 46.78 | 699.00 | 2308.00 |
| 23 | 2026-11-17T16:47:02.952Z | 44.0 | 31.00 | 47.00 | 1002.79 | 26.35 | 46.82 | 699.00 | 2307.00 |
| 24 | 2026-11-17T16:47:04.952Z | 46.0 | 31.00 | 47.00 | 1002.81 | 26.31 | 46.87 | 699.00 | 2310.00 |
| 25 | 2026-11-17T16:47:06.952Z | 48.0 | 31.00 | 47.00 | 1002.84 | 26.30 | 46.96 | 699.00 | 2310.00 |
| 26 | 2026-11-17T16:47:08.952Z | 50.0 | 31.10 | 46.00 | 1002.80 | 26.27 | 47.04 | 699.00 | 2309.00 |
| 27 | 2026-11-17T16:47:10.952Z | 52.0 | 31.10 | 46.00 | 1002.82 | 26.25 | 47.12 | 699.00 | 2309.00 |
| 28 | 2026-11-17T16:47:12.952Z | 54.0 | 31.20 | 46.00 | 1002.76 | 26.23 | 47.16 | 699.00 | 2307.00 |
| 29 | 2026-11-17T16:47:14.952Z | 56.0 | 31.20 | 46.00 | 1002.81 | 26.21 | 47.19 | 699.00 | 2309.00 |
| 30 | 2026-11-17T16:47:16.952Z | 58.0 | 31.20 | 46.00 | 1002.80 | 26.19 | 47.28 | 699.00 | 2309.00 |

## Result

| Check | Result |
|---|---|
| `dht11.temperature`: at least 30 dated valid readings (30) | PASS |
| `dht11.humidity`: at least 30 dated valid readings (30) | PASS |
| `bme280.pressure`: at least 30 dated valid readings (30) | PASS |
| `light.raw`: at least 30 dated valid readings (30) | PASS |
| Every failed read recorded as empty with explicit quality (0 failed reads) | PASS |

## To fill in by hand

- Sensor models and Grove ports: DHT11 on GPIO 5 (D5); Grove BME280 on the second Grove I2C port (the LCD is on the first), chip id 0x60 read at 0x76; Grove light sensor on A0. Photo of the wiring: PENDING.
- Condition applied: none (baseline). Indoor room, artificial light.
- Reference values: PENDING (room thermometer, pressure of a nearby weather station at the same time).
- Observations and limitations:
  - The four required channels give 30 dated valid readings each; no failed read.
  - **The DHT11 reads 4–5 degC above the BME280** placed next to it, and rises steadily (30.2 → 31.2 degC in one minute) while the BME280 stays at 26.2–27.0 degC. Its first reading (26.4 degC) matches the BME280. Possible causes: self-heating with a read every 2 s, or heat from the Pi. To be checked with a longer interval before deciding which sensor publishes `temperature` (#14).
  - DHT11 humidity has a resolution of 1 %; the BME280 gives 46.4 % ± 0.5 against 47.5 % for the DHT11.
  - Pressure is stable (1002.80 ± 0.03 hPa); it is absolute pressure, not reduced to sea level.
  - Light in raw units (per mille of the supply), not lux.
  - Pending: two-condition phases and disconnection (steps 2–3).
