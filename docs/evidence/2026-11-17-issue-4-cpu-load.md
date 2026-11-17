# Environmental sensors validation — idle, cpu-load

- **Date (UTC):** 2026-11-17T17:11:37Z
- **Run by:** Erik Eguskiza (eeguskiza), over SSH, unattended
- **Reviewed by:** _fill in_
- **Issue / PR:** #4 / #51
- **Commit:** ed5a5c2
- **Hardware:** Raspberry Pi 5 Model B Rev 1.0; Debian GNU/Linux 13 (trixie); aarch64
- **Relevant versions:** Python 3.13.5; kernel 6.18.60+rpt-rpi-2712; arecord: version 1.2.14 by Jaroslav Kysela <perex@perex.cz>
- **Procedure:** `PYTHONPATH=src python3 -m txori_kantua.environment.env_check --phase idle --phase cpu-load --phase-wait 180`

## Setup

- Rounds per phase: 30, every 2 s; phases: `idle`, `cpu-load`
- DHT11 on GPIO 5 (BCM), driver `txori_kantua.dht11` (lgpio)
- BME280 on I2C bus 1, found at `0x76` (probed 0x76, 0x77); forced mode, oversampling x1, filter off
- Grove light sensor on analogue port A0: Grove Base Hat for Raspberry Pi. Value in **raw** per mille of the supply (0..1000), not lux

## Summary

| Phase | Channel | ok | unavailable | error | Min | Mean | Max | Std dev | First failure |
|---|---|---|---|---|---|---|---|---|---|
| idle | `dht11.temperature` (degC) | 30 | 0 | 0 | 36.00 | 36.32 | 36.40 | 0.083 |  |
| idle | `dht11.humidity` (percent) | 30 | 0 | 0 | 36.00 | 36.10 | 38.00 | 0.403 |  |
| idle | `bme280.pressure` (hPa) | 30 | 0 | 0 | 1002.64 | 1002.69 | 1002.77 | 0.033 |  |
| idle | `bme280.temperature` (degC) | 30 | 0 | 0 | 25.02 | 25.04 | 25.06 | 0.011 |  |
| idle | `bme280.humidity` (percent) | 30 | 0 | 0 | 49.76 | 49.84 | 49.89 | 0.027 |  |
| idle | `light.raw` (raw) | 30 | 0 | 0 | 699.00 | 699.17 | 700.00 | 0.379 |  |
| idle | `light.millivolts` (mV) | 30 | 0 | 0 | 2305.00 | 2308.50 | 2310.00 | 0.974 |  |
| cpu-load | `dht11.temperature` (degC) | 0 | 30 | 0 |  | | |  | DHT11: only 18 pulses received |
| cpu-load | `dht11.humidity` (percent) | 0 | 30 | 0 |  | | |  | DHT11: only 18 pulses received |
| cpu-load | `bme280.pressure` (hPa) | 30 | 0 | 0 | 1002.69 | 1002.76 | 1002.85 | 0.049 |  |
| cpu-load | `bme280.temperature` (degC) | 30 | 0 | 0 | 24.65 | 24.80 | 24.96 | 0.097 |  |
| cpu-load | `bme280.humidity` (percent) | 30 | 0 | 0 | 49.68 | 49.88 | 50.18 | 0.169 |  |
| cpu-load | `light.raw` (raw) | 30 | 0 | 0 | 693.00 | 698.97 | 702.00 | 1.650 |  |
| cpu-load | `light.millivolts` (mV) | 30 | 0 | 0 | 2294.00 | 2308.20 | 2319.00 | 6.599 |  |

## Response to condition changes

Difference of each phase mean against `idle`. A channel *responds* when the difference exceeds both 3 standard deviations of the noise and the sensor resolution.

| Channel | idle | cpu-load | Threshold | Response |
|---|---|---|---|---|
| `dht11.temperature` | 36.32 | no data | | not comparable |
| `dht11.humidity` | 36.10 | no data | | not comparable |
| `bme280.pressure` | 1002.69 | 1002.76 (+0.08) | 0.15 | no clear change |
| `bme280.temperature` | 25.04 | 24.80 (-0.24) | 0.50 | no clear change |
| `bme280.humidity` | 49.84 | 49.88 (+0.04) | 1.00 | no clear change |
| `light.raw` | 699.17 | 698.97 (-0.20) | 5.00 | no clear change |
| `light.millivolts` | 2308.50 | 2308.20 (-0.30) | 19.80 | no clear change |

## Readings — idle

| # | UTC | t (s) | `dht11.temperature` | `dht11.humidity` | `bme280.pressure` | `bme280.temperature` | `bme280.humidity` | `light.raw` | `light.millivolts` |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-17T17:06:40.782Z | 180.0 | 36.00 | 38.00 | 1002.74 | 25.06 | 49.86 | 699.00 | 2308.00 |
| 2 | 2026-11-17T17:06:42.782Z | 182.0 | 36.40 | 36.00 | 1002.70 | 25.05 | 49.89 | 699.00 | 2308.00 |
| 3 | 2026-11-17T17:06:44.782Z | 184.0 | 36.40 | 36.00 | 1002.70 | 25.05 | 49.83 | 699.00 | 2309.00 |
| 4 | 2026-11-17T17:06:46.782Z | 186.0 | 36.40 | 36.00 | 1002.66 | 25.05 | 49.85 | 699.00 | 2309.00 |
| 5 | 2026-11-17T17:06:48.782Z | 188.0 | 36.40 | 36.00 | 1002.71 | 25.04 | 49.85 | 700.00 | 2308.00 |
| 6 | 2026-11-17T17:06:50.782Z | 190.0 | 36.40 | 36.00 | 1002.68 | 25.04 | 49.83 | 700.00 | 2308.00 |
| 7 | 2026-11-17T17:06:52.782Z | 192.0 | 36.40 | 36.00 | 1002.74 | 25.06 | 49.84 | 699.00 | 2309.00 |
| 8 | 2026-11-17T17:06:54.782Z | 194.0 | 36.40 | 36.00 | 1002.73 | 25.04 | 49.84 | 699.00 | 2309.00 |
| 9 | 2026-11-17T17:06:56.782Z | 196.0 | 36.40 | 36.00 | 1002.64 | 25.05 | 49.85 | 699.00 | 2309.00 |
| 10 | 2026-11-17T17:06:58.782Z | 198.0 | 36.40 | 36.00 | 1002.77 | 25.04 | 49.87 | 699.00 | 2310.00 |
| 11 | 2026-11-17T17:07:00.782Z | 200.0 | 36.40 | 36.00 | 1002.69 | 25.03 | 49.87 | 699.00 | 2309.00 |
| 12 | 2026-11-17T17:07:02.782Z | 202.0 | 36.30 | 36.00 | 1002.67 | 25.04 | 49.83 | 699.00 | 2309.00 |
| 13 | 2026-11-17T17:07:04.782Z | 204.0 | 36.30 | 36.00 | 1002.64 | 25.03 | 49.84 | 699.00 | 2309.00 |
| 14 | 2026-11-17T17:07:06.782Z | 206.0 | 36.30 | 36.00 | 1002.68 | 25.02 | 49.83 | 700.00 | 2309.00 |
| 15 | 2026-11-17T17:07:08.782Z | 208.0 | 36.30 | 36.00 | 1002.70 | 25.04 | 49.83 | 699.00 | 2308.00 |
| 16 | 2026-11-17T17:07:10.782Z | 210.0 | 36.30 | 36.00 | 1002.69 | 25.03 | 49.80 | 699.00 | 2308.00 |
| 17 | 2026-11-17T17:07:12.782Z | 212.0 | 36.30 | 36.00 | 1002.69 | 25.03 | 49.86 | 699.00 | 2307.00 |
| 18 | 2026-11-17T17:07:14.782Z | 214.0 | 36.30 | 36.00 | 1002.66 | 25.03 | 49.87 | 699.00 | 2308.00 |
| 19 | 2026-11-17T17:07:16.782Z | 216.0 | 36.30 | 36.00 | 1002.67 | 25.04 | 49.85 | 699.00 | 2307.00 |
| 20 | 2026-11-17T17:07:18.782Z | 218.0 | 36.30 | 36.00 | 1002.74 | 25.04 | 49.88 | 699.00 | 2309.00 |
| 21 | 2026-11-17T17:07:20.782Z | 220.0 | 36.30 | 36.00 | 1002.73 | 25.04 | 49.87 | 699.00 | 2309.00 |
| 22 | 2026-11-17T17:07:22.782Z | 222.0 | 36.30 | 36.00 | 1002.67 | 25.05 | 49.84 | 699.00 | 2309.00 |
| 23 | 2026-11-17T17:07:24.782Z | 224.0 | 36.30 | 36.00 | 1002.67 | 25.05 | 49.84 | 700.00 | 2308.00 |
| 24 | 2026-11-17T17:07:26.782Z | 226.0 | 36.30 | 36.00 | 1002.68 | 25.06 | 49.84 | 699.00 | 2309.00 |
| 25 | 2026-11-17T17:07:28.782Z | 228.0 | 36.30 | 36.00 | 1002.69 | 25.05 | 49.87 | 699.00 | 2308.00 |
| 26 | 2026-11-17T17:07:30.782Z | 230.0 | 36.30 | 36.00 | 1002.65 | 25.06 | 49.79 | 699.00 | 2309.00 |
| 27 | 2026-11-17T17:07:32.782Z | 232.0 | 36.30 | 36.00 | 1002.64 | 25.05 | 49.76 | 699.00 | 2309.00 |
| 28 | 2026-11-17T17:07:34.782Z | 234.0 | 36.30 | 36.00 | 1002.66 | 25.04 | 49.81 | 700.00 | 2305.00 |
| 29 | 2026-11-17T17:07:36.782Z | 236.0 | 36.20 | 36.00 | 1002.69 | 25.05 | 49.84 | 699.00 | 2310.00 |
| 30 | 2026-11-17T17:07:38.782Z | 238.0 | 36.20 | 37.00 | 1002.65 | 25.06 | 49.82 | 699.00 | 2309.00 |

## Readings — cpu-load

| # | UTC | t (s) | `dht11.temperature` | `dht11.humidity` | `bme280.pressure` | `bme280.temperature` | `bme280.humidity` | `light.raw` | `light.millivolts` |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-17T17:10:38.847Z | 418.1 | _unavailable_ | _unavailable_ | 1002.85 | 24.95 | 49.70 | 699.00 | 2319.00 |
| 2 | 2026-11-17T17:10:40.847Z | 420.1 | _unavailable_ | _unavailable_ | 1002.77 | 24.96 | 49.68 | 699.00 | 2313.00 |
| 3 | 2026-11-17T17:10:42.847Z | 422.1 | _unavailable_ | _unavailable_ | 1002.77 | 24.94 | 49.70 | 702.00 | 2294.00 |
| 4 | 2026-11-17T17:10:44.847Z | 424.1 | _unavailable_ | _unavailable_ | 1002.83 | 24.92 | 49.70 | 699.00 | 2307.00 |
| 5 | 2026-11-17T17:10:46.847Z | 426.1 | _unavailable_ | _unavailable_ | 1002.82 | 24.92 | 49.69 | 698.00 | 2309.00 |
| 6 | 2026-11-17T17:10:48.847Z | 428.1 | _unavailable_ | _unavailable_ | 1002.80 | 24.91 | 49.68 | 700.00 | 2306.00 |
| 7 | 2026-11-17T17:10:50.847Z | 430.1 | _unavailable_ | _unavailable_ | 1002.76 | 24.90 | 49.71 | 699.00 | 2308.00 |
| 8 | 2026-11-17T17:10:52.847Z | 432.1 | _unavailable_ | _unavailable_ | 1002.83 | 24.89 | 49.72 | 700.00 | 2307.00 |
| 9 | 2026-11-17T17:10:54.847Z | 434.1 | _unavailable_ | _unavailable_ | 1002.80 | 24.87 | 49.74 | 697.00 | 2313.00 |
| 10 | 2026-11-17T17:10:56.847Z | 436.1 | _unavailable_ | _unavailable_ | 1002.85 | 24.87 | 49.76 | 693.00 | 2294.00 |
| 11 | 2026-11-17T17:10:58.847Z | 438.1 | _unavailable_ | _unavailable_ | 1002.81 | 24.86 | 49.79 | 698.00 | 2314.00 |
| 12 | 2026-11-17T17:11:00.847Z | 440.1 | _unavailable_ | _unavailable_ | 1002.77 | 24.86 | 49.78 | 699.00 | 2305.00 |
| 13 | 2026-11-17T17:11:02.847Z | 442.1 | _unavailable_ | _unavailable_ | 1002.78 | 24.85 | 49.78 | 700.00 | 2294.00 |
| 14 | 2026-11-17T17:11:04.847Z | 444.1 | _unavailable_ | _unavailable_ | 1002.80 | 24.82 | 49.80 | 698.00 | 2319.00 |
| 15 | 2026-11-17T17:11:06.847Z | 446.1 | _unavailable_ | _unavailable_ | 1002.80 | 24.81 | 49.82 | 698.00 | 2306.00 |
| 16 | 2026-11-17T17:11:08.847Z | 448.1 | _unavailable_ | _unavailable_ | 1002.75 | 24.79 | 49.87 | 700.00 | 2308.00 |
| 17 | 2026-11-17T17:11:10.847Z | 450.1 | _unavailable_ | _unavailable_ | 1002.78 | 24.78 | 49.88 | 700.00 | 2308.00 |
| 18 | 2026-11-17T17:11:12.847Z | 452.1 | _unavailable_ | _unavailable_ | 1002.72 | 24.77 | 49.93 | 698.00 | 2309.00 |
| 19 | 2026-11-17T17:11:14.847Z | 454.1 | _unavailable_ | _unavailable_ | 1002.73 | 24.76 | 49.98 | 699.00 | 2308.00 |
| 20 | 2026-11-17T17:11:16.847Z | 456.1 | _unavailable_ | _unavailable_ | 1002.70 | 24.75 | 50.01 | 698.00 | 2304.00 |
| 21 | 2026-11-17T17:11:18.847Z | 458.1 | _unavailable_ | _unavailable_ | 1002.74 | 24.74 | 49.98 | 702.00 | 2308.00 |
| 22 | 2026-11-17T17:11:20.847Z | 460.1 | _unavailable_ | _unavailable_ | 1002.70 | 24.73 | 50.00 | 699.00 | 2317.00 |
| 23 | 2026-11-17T17:11:22.847Z | 462.1 | _unavailable_ | _unavailable_ | 1002.70 | 24.71 | 50.01 | 698.00 | 2318.00 |
| 24 | 2026-11-17T17:11:24.847Z | 464.1 | _unavailable_ | _unavailable_ | 1002.72 | 24.70 | 50.03 | 699.00 | 2309.00 |
| 25 | 2026-11-17T17:11:26.847Z | 466.1 | _unavailable_ | _unavailable_ | 1002.75 | 24.69 | 50.07 | 699.00 | 2308.00 |
| 26 | 2026-11-17T17:11:28.847Z | 468.1 | _unavailable_ | _unavailable_ | 1002.70 | 24.69 | 50.09 | 699.00 | 2308.00 |
| 27 | 2026-11-17T17:11:30.847Z | 470.1 | _unavailable_ | _unavailable_ | 1002.71 | 24.68 | 50.15 | 699.00 | 2316.00 |
| 28 | 2026-11-17T17:11:32.847Z | 472.1 | _unavailable_ | _unavailable_ | 1002.79 | 24.68 | 50.15 | 702.00 | 2300.00 |
| 29 | 2026-11-17T17:11:34.850Z | 474.1 | _unavailable_ | _unavailable_ | 1002.69 | 24.67 | 50.15 | 699.00 | 2309.00 |
| 30 | 2026-11-17T17:11:36.847Z | 476.1 | _unavailable_ | _unavailable_ | 1002.69 | 24.65 | 50.18 | 699.00 | 2308.00 |

## Result

| Check | Result |
|---|---|
| `dht11.temperature`: at least 30 dated valid readings (30) | PASS |
| `dht11.humidity`: at least 30 dated valid readings (30) | PASS |
| `bme280.pressure`: at least 30 dated valid readings (60) | PASS |
| `light.raw`: at least 30 dated valid readings (60) | PASS |
| Every failed read recorded as empty with explicit quality (60 failed reads) | PASS |

## To fill in by hand

- Condition applied: remote, nobody at the Pi. After the SoC cooled below
  55 degC, the idle phase ran with the Pi unloaded. Four busy loops
  (`sh -c 'while :; do :; done'`, one per core) then ran from 17:07:45 UTC
  for 300 s, covering the second wait and the `cpu-load` phase. SoC
  temperature: 54.0 degC at load start, 84.8 degC at the end of the phase.
  `txori-kantua.service` stopped.
- Reference values: none (no operator).
- Observations and limitations:
  - **Under full CPU load the DHT11 failed all 30 reads** ("only 18 pulses
    received"): the lgpio edge-capture driver loses edges when the four cores
    are busy. The failures were recorded as `unavailable` with an empty value,
    never as 0. This matters for #16: BirdNET inference will load the CPU while
    the DHT11 is read. Mitigations to evaluate: use the BME280 for temperature
    and humidity, retry with backoff, or read the DHT11 at a higher priority.
  - The DHT11 idle reading (36.3 degC, 36 %) is again far from the BME280
    (25.0 degC, 49.8 %), consistent with the baseline report.
  - **The heat of the SoC did not reach the BME280** (−0.24 degC, below its
    threshold). The module is not close to the SoC, so this test is **not**
    the condition change the issue asks for. A local change by an operator
    (breath, covering the light sensor) is still pending.
  - Pressure and light did not change, as expected for this condition.
