# Elena — Sprint 2: sensors and LCD

Scope checked against the assigned open issues on 25 November 2026:
[#14](https://github.com/elenaatorralbo/txori-kantua/issues/14) and
[#22](https://github.com/elenaatorralbo/txori-kantua/issues/22).
This is implementation and a reproducible procedure, **not physical acceptance**.

## Environmental publishing (#14)

`txori-sensors` (or `python -m txori_kantua.environment.publisher`) reads
BME280 temperature/humidity/pressure and Grove A0 light. The source decision is
explicit: [CPU-load evidence](evidence/2026-11-17-issue-4-cpu-load.md) showed
DHT11 failures under load. There is no silent sensor substitution.

| Metric | Source | Unit |
|---|---|---|
| temperature | BME280 | degC |
| humidity | BME280 | percent |
| pressure | BME280 | hPa |
| light | Grove ADC A0 | raw, 0–1000; not lux |

The existing contract validator and QoS 1 transport are reused. Each observation
gets its own UUID and UTC timestamp. An unavailable sensor produces null with
quality `unavailable`; an invalid reading produces null with quality `error`.
Other sensors continue. An unplugged analogue light sensor cannot reliably be
distinguished from darkness; absence of the ADC itself is detectable.

Load the external `sensors` MQTT credentials and `TXORI_STATION_ID`, then run:

```sh
python -m txori_kantua.environment.publisher --interval 30 --seconds 1800 \
  --bme-address 0x76 --light-channel 0 > /tmp/txori-sensors-summary.json \
  2> /tmp/txori-sensors.log
```

The final JSON reports sample counts, per-channel quality, elapsed seconds,
accepted messages, confirmed PUBACKs, unconfirmed messages and queue drops.
Counters with zero occurrences may be absent. `accepted` means queued;
`confirmed` means the broker acknowledged within two seconds. `unconfirmed`
may be delivered later, so it is neither proof of delivery nor proof of loss.
No second retry queue is introduced. Logs include event IDs for correlation
with ingest/API. The duration bounds the sampling window; the last hardware
read or bounded acknowledgement can finish after it.

For acceptance, retain the dated summary and correlate IDs with storage. Record
models, connections, commit and runtime versions. Run 30 real minutes with all
four channels; then follow the powered-off disconnection procedure in
[environment sensors](environment-sensors.md) and verify unaffected channels.
The software test uses an accelerated clock and a fake broker: it does not
satisfy this physical criterion.

## LCD integration (#22)

`txori-lcd` (or `python -m txori_kantua.lcd_station`) subscribes to validated
detections using the existing `station` MQTT account. A lock serializes callbacks
and UI updates; only the latest detection is retained. Duplicate/older events
are ignored. A disconnected broker shows an ES/EU/EN offline message; events
older than five minutes show the no-data message. MQTT reconnection is automatic.

GPIO offsets, active levels, PIR warmup and debounce must be supplied explicitly
from the observed wiring. The 20 ms polling loop updates only changed rows or
backlight state. A held PIR signal generates one activation; another rising
edge or a debounced touch renews the 20-second timeout. Touch advances pages,
then ES → EU → EN. Each page has two padded 16-character ASCII rows; accents
are transliterated and long names paginated. Errors in one GPIO read do not
hide the other input. Shutdown attempts backlight-off and releases resources.

### Hardware blocker and adapter interface

The [17 November evidence](evidence/2026-11-17-pipeline/validation.md) records
PIR on D16, no touch connected, and a no-op `_backlight_on` in the installed
JHD1802 driver. A text clear or display-off command does not prove that the
backlight is off. **No working physical backlight driver is included in this
change**, because the actual controllable hardware has not been identified.

`--lcd-factory module:callable` must return a hardware adapter implementing:

- `write_rows(rows)`: write the two padded 16-character rows.
- `set_backlight(enabled)`: physically switch the light on/off.
- `close()`: release the device/bus.

The callable takes no arguments; board configuration belongs in that adapter.
It must not allocate outputs on guessed pins. Validate its on/off operation on
the exact LCD first. The application checks the interface, but cannot prove
that a driver method changes the hardware. A missing method fails at startup.
No default factory silently wraps the known no-op JHD1802 method.

After providing that adapter and confirming both inputs, run (replace all
uppercase wiring placeholders with measured values):

```sh
python -m txori_kantua.lcd_station \
  --chip CHIP --pir-pin PIR_BCM --touch-pin TOUCH_BCM \
  --pir-active PIR_LEVEL --touch-active TOUCH_LEVEL \
  --warmup-ms WARMUP_MS --debounce-ms DEBOUNCE_MS \
  --lcd-factory verified_board:create_lcd
```

Load the external `station` credentials and `TXORI_STATION_ID` first. Do not run
this process concurrently with the legacy `txori-kantua.service`, which owns the
same LCD. The existing recovery service is unchanged. Service deployment and
restart behaviour remain part of the later deployment work.

### Translation catalogue

The bundled `bird_names.json` covers the five evaluation-corpus species.
ES/EU names were checked on 25 November against the
[Comité Ornitológico de Euskadi list](https://ornitologia.eus/es/listado-aves/).
English names follow the existing attributed recording titles in
`audio/corpus.json`. This is a small display catalogue, not a regional inference
allowlist. Team review is pending. Additional species or absent translations
fall back to the scientific name. `--catalogue PATH` replaces the catalogue
with a validated JSON mapping of scientific name to `es`, `eu`, `en` strings.

### Acceptance remaining

Record ten physical PIR/touch cycles, debounce behaviour, the real backlight
turning off at 20 ±1 seconds, long-name pagination and startup recovery. Exercise
fresh and stale detection metadata and a broker outage/reconnect. Identify any
synthetic metadata in the report. Obtain another member's review and merge the
PR before closing #14/#22. Neither issue is marked done by local tests.

## Local verification

```sh
.venv/bin/python -m pytest -q
```

New tests exercise simulated 30-minute environmental publication, unique IDs,
quality isolation, queue rejection and recovery; MQTT-to-screen delivery,
invalid messages, station isolation, stale data, disconnection/reconnection,
long names, language fallback, GPIO failures, timeout calls and cleanup after
an I2C write failure. No new physical measurements were taken in this session.

On 25 November 2026, the local macOS suite returned **579 passed, 10 skipped**
(4.63 s). The skips require a configured live broker/restart command or BirdNET
model. Both module CLI help commands and `git diff --check` passed. These results
apply to the code accompanying this guide; no Raspberry deployment was performed.
