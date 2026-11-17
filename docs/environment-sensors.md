# Environmental sensors: validation procedure (issue #4)

Tool: `python -m txori_kantua.environment.env_check`. It reads every channel
once per round, dates each sample (UTC and seconds since start) and writes a
Markdown report with the [evidence header](evidence/README.md) to stdout.
**This document is a procedure, not evidence.** Nothing here has run on the Pi
until a report exists in `docs/evidence/`.

## Sensors and channels

| Sensor | Connection | Channels | Unit | Range treated as valid |
|---|---|---|---|---|
| DHT11 | GPIO 5 (BCM), existing `txori_kantua.dht11` driver | `dht11.temperature`, `dht11.humidity` | degC, percent | 0..50 degC, 20..90 % (DHT11 datasheet) |
| Grove BME280 | I2C bus 1, address 0x76 or 0x77 (probed, chip id 0x60 checked) | `bme280.pressure` (+ `bme280.temperature`, `bme280.humidity` as cross-check) | hPa, degC, percent | 300..1100 hPa, -40..85 degC |
| Grove light sensor | Base Hat analogue port A0 (`--light-channel`), ADC at 0x08 or 0x04 | `light.raw` (+ `light.millivolts` as evidence) | raw per mille of the supply (0..1000) | 0..1000 |

The BME280 runs in forced mode with x1 oversampling and no filter: one
measurement per read, asleep in between (less self-heating). The compensation
is the datasheet's floating-point formula; tests check it against the Bosch
worked example and the Bosch integer reference.

**Light is not lux.** The Grove light sensor is a photoresistor divider; the
Base Hat reports its voltage. Converting to lux needs the exact cell curve and
a calibration against a luxmeter, which we do not have. The MQTT contract
allows `raw` for exactly this case.

## Failure handling: never a zero

A read that fails is a row with an empty value and an explicit quality, using
the vocabulary of the [environment contract](mqtt.md):

- `unavailable`: the sensor does not answer (I2C NACK, DHT11 sends no pulses,
  GPIO cannot be opened, Base Hat ADC absent).
- `error`: it answered, but the value fails validation (DHT11 checksum, BME280
  "skipped" raw value, measurement not finished, value outside the range above).

Two cases where a failure would otherwise look like data:

- A DHT11 frame of all zeros has a **valid checksum**, so a stuck data line
  would read "0 degC, 0 %". The humidity range (20..90 %) turns it into `error`.
- An I2C bus pulled low makes the BME280 read all zeros; the compensated
  values fall outside the sensor range and become `error`.

Sources reconnect on the next read after a failure, so plugging a sensor back
in shows up in the same run.

**Limitation, analogue light:** an unplugged analogue port is not reported by
the ADC. Its value floats or drops towards 0, which is indistinguishable from
darkness. Only the absence of the Base Hat ADC is detected. The report must
record this rather than claim automatic disconnection detection for light.

## Procedure on the Pi

Prerequisites: I2C enabled (`raspi-config`), `smbus2` and `lgpio` importable by
the interpreter used (`python3 -c "import smbus2, lgpio"`), the repository at
the commit under test, and the station service stopped so it does not hold the
DHT11 GPIO:

```sh
sudo systemctl stop txori-kantua.service
```

Restart it at the end with `sudo systemctl start txori-kantua.service`.
Copy the [report template](templates/issue-4-environment.md) for the hand-written
parts. Name each output following the evidence convention.

1. **Baseline, 30 readings per channel** (about 1 minute):

   ```sh
   python3 -m txori_kantua.environment.env_check > docs/evidence/YYYY-MM-DD-issue-4-baseline.md
   ```

2. **Two conditions per sensor.** Each phase takes 30 rounds every 2 s. The
   command prompts between phases on stderr and waits for Enter (or
   `--phase-wait` seconds when there is no terminal).

   ```sh
   # Light: cover the sensor completely, then light it with a phone torch at ~10 cm.
   python3 -m txori_kantua.environment.env_check --no-dht --no-bme280 \
       --phase covered --phase lit > docs/evidence/YYYY-MM-DD-issue-4-light.md
   # Temperature/humidity: room air, then breathe gently on both sensors / hold a warm hand near them.
   python3 -m txori_kantua.environment.env_check --phase room --phase breath \
       > docs/evidence/YYYY-MM-DD-issue-4-temp-humidity.md
   # Pressure: sensor on the table, then raised ~2 m (≈ -0.24 hPa; resolution 0.12 hPa).
   python3 -m txori_kantua.environment.env_check --no-dht --no-light \
       --phase table --phase raised > docs/evidence/YYYY-MM-DD-issue-4-pressure.md
   ```

   The *Response* table compares each phase against the first with a threshold
   of 3 standard deviations of the noise or the sensor resolution, whichever
   is larger. Record the reference values (room thermometer, pressure of a
   nearby weather station) to judge whether the range is plausible.

3. **Disconnection.** Follow the [session guide](sprint1-hardware-session.md):
   power off the Pi before touching the Grove cables. Unplug one sensor, boot,
   and run a short phase; then power off, plug it back in and repeat.

   ```sh
   python3 -m txori_kantua.environment.env_check --samples 5 --phase bme280-unplugged \
       > docs/evidence/YYYY-MM-DD-issue-4-disconnect.md
   ```

   Expected: the unplugged sensor shows `unavailable` in every round with the
   error message, an empty value and no 0; the other sensors keep reading. For
   the DHT11, unplugging gives "only N pulses received". For light, record what
   the ADC actually shows (see the limitation above).

## Acceptance criteria mapping

| Criterion of #4 | Evidence |
|---|---|
| At least 30 dated readings per channel | Baseline report: *Result* rows per channel, *Readings* table with UTC per round |
| Condition changes produce a documented response and plausible ranges | Two-phase reports: *Response* table and reference values written by hand |
| Disconnection returns an explicit error; zero is never recorded as valid | Disconnection report: `unavailable`/`error` rows with message; *Result* row on failed reads; unit tests in `tests/environment/` |
| No lux attributed to an uncalibrated ADC | Light is reported in `raw` (per mille) and millivolts only |

Open decision for [#14](https://github.com/elenaatorralbo/txori-kantua/issues/14):
which sensor publishes `temperature` and `humidity` (DHT11 or BME280). The
reports give both side by side to decide with data; the BME280 is more precise
on paper (±1 degC, ±3 %RH against ±2 degC, ±5 %RH).
