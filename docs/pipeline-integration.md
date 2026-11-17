# Pipeline integration — 17 November 2026

[Verification evidence](evidence/2026-11-17-pipeline/validation.md).

This integration branch combines the existing MQTT implementation and the open
health/daily-aggregate PRs. It does not replace their independent review. No
release or physical acceptance is implied by a passing software test.

## Implemented connections

- `environment.publisher`: BME280 temperature/humidity/pressure and Grove A0
  light, every 30 seconds by default. Light is raw 0..1000. A failed channel is
  null/unavailable. BME280 is selected explicitly because existing #4 evidence
  records DHT11 failures under CPU load; it never silently substitutes devices.
- `ingest`: persistent MQTT session, manual QoS 1 acknowledgement **after** SQLite
  commit, bounded queue (1,000 metadata events), exponential storage retry.
  Invalid messages are counted without saving or logging their contents.
- `storage`: WAL, global event UUID identity, indexed UTC milliseconds, read-only
  readers, SQL views for dashboards, consistent `VACUUM INTO` backup. Reusing an
  ID for different content is rejected rather than rewriting the observation.
- `api.create_app(path)`: `/api/v1/health`, `/detections`, `/environment`, and
  `/summaries/daily`. UTC half-open intervals, 31-day raw query cap, 500-row page
  cap, query-bound cursors, 92-day aggregate cap; unavailable storage returns 503.
- `audio.pipeline`: bounded queue of two 3-second mono 48 kHz S16_LE windows,
  oldest-drop policy and wiping, stable detection IDs, model-error counters
  separate from empty windows. This is a library, not a deployed capture daemon.
- `audio.filtering`: explicit reviewed region/month allowlists and inclusive
  score threshold. Missing context fails closed. No real regional catalogue or
  quality calibration is asserted; confidence remains a model score.
- `display`: PIR/touch state integration, ES/EU/EN messages and scientific-name
  fallback, stale/out-of-order detection handling, 20-second logical timeout.
  It requires a hardware adapter capable of switching the actual backlight.

## Reproduce software verification

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
# Linux; broker binaries installed but no production configuration required:
.venv/bin/python tools/verify_pipeline.py \
  --mosquitto /usr/sbin/mosquitto --passwd /usr/bin/mosquitto_passwd
```

The integration verifier generates temporary passwords, starts a broker on a
random loopback port, runs the live ACL tests and uses **synthetic detection
metadata**. It sends the same event three times to two independent consumers,
checks one SQLite record through the API, restarts the broker and checks recovery.
Its temporary credentials, database and log are removed when it exits.

The workflow runs software tests on Python 3.11 and 3.13 and the isolated broker
integration on Linux. Hardware/model acceptance remains separate.

## Running services from a checkout

Configure Mosquitto following [broker.md](broker.md). Each process loads only its
own external credential file; do not paste secrets into commands, Git or logs.
`TXORI_STATION_ID` must match across services. `TXORI_DATABASE` points to an
existing writable directory owned by the ingest user. The API account needs
read access to the database and WAL files; it never creates a missing database.

```bash
# Ingest, with its own MQTT environment already loaded:
TXORI_STATION_ID=station-01 TXORI_DATABASE=/var/lib/txori-kantua/events.sqlite \
  python -m txori_kantua.ingest
# Sensors, with the sensors credential loaded, after confirming the wiring:
TXORI_STATION_ID=station-01 python -m txori_kantua.environment.publisher
# Local development API (Flask's server is not the production deployment):
flask --app 'txori_kantua.api:create_app("/var/lib/txori-kantua/events.sqlite")' \
  run --host 127.0.0.1 --port 5000
```

Use `Store(path).backup(destination)` from the sole writer process for a
consistent metadata copy. The tests reopen that copy and run `integrity_check`.
No restore test should overwrite a live database. Stop writers before an
operational restore; validate a restored copy separately first.

## Retention and failure behaviour

Every minute ingest performs bounded maintenance: at most one expired day's
projection and up to 1,000 deletions per event kind. Retention follows the
30-day environment/health and 90-day detection/availability proposal. A daily
projection must exist before raw deletion. A day becomes sealed on first purge;
late corrections to a sealed day are rejected explicitly, preserving historical
summaries. Rebuilding such a day requires the archived raw data offline. This is
an explicit limitation pending agreement on historical correction policy.

Raw metadata remains immutable within retention. A retry retains event ID and
observation time. Storage errors hold the current message without acknowledging
it; the network queue remains bounded. A full queue requests reconnection after
room becomes available so the persistent broker session can redeliver. Broker
queue limits still imply possible loss after a sufficiently long outage; this
is not an unlimited durable delivery guarantee. The planned 60-second outage,
low-disk test and resource-budget measurements remain acceptance work for #26.

Daily coverage currently counts minutes with **any** station event. That does
not prove that audio capture/inference ran for those minutes. Zero detections
must not be described as ecological absence; inference-specific coverage remains
necessary before rate-based analysis. No mixed raw/lux series should be aggregated
as one unit without a documented migration.

## Physical observations in this session

- SSH accessible, station service initially active, then stopped by Elena for
  validation. USB capture device appears as `USB Advanced Audio Device`.
- Elena confirmed two full LCD rows and `Herrerillo comun` / `Cyanistes caerul`
  after commands through the installed JHD1802 driver. This is operator evidence,
  **not a substitute for the required photograph/video**.
- The installed JHD1802 `_backlight_on` method is `pass`. Software timeout alone
  cannot establish physical backlight shutdown. Screen model/controller needs
  identification before choosing a compatible implementation.
- Elena identifies PIR on D16; no touch sensor is connected. Ten observed cycles,
  polarities, stabilization and fault behaviour remain unverified.
- `/dev/zram0` has `/dev/loop0` backing `/var/swap`. No microphone capture was
  started while that disk-writeback path remained active. Temporary `swapoff`
  alone would not establish persistence-safe configuration after reboot.

## Issue closure gates

| Issues | Current result / outstanding criterion |
|---|---|
| #13, #18 | Real isolated broker ACL/delivery/restart verified; production installation, review and integration pending |
| #19, #20 | Storage/API implemented and contract, restart, backup and error tests pass; review/integration pending |
| #14 | Four-channel publisher implemented; real 30-minute publication run pending |
| #15–17 | Queue, inference normalization and deterministic context filters implemented; real corpus, budgets and 30-minute privacy run pending |
| #22 | State machine tested; backlight adapter, touch hardware and reviewed names pending |
| #24, #28 | Existing PR implementations included and review corrections applied (installed venv path, unknown analyzed-audio coverage); deployed health panel/trend dashboard pending |
| #26, #27 | Retry, queue limits, real broker tests and CI definition added; full fault matrix/hosted CI pending |
| #1, #3–8, #11 | Operator evidence/measurements still required; physical constraints above apply |
| #12 | Team capacity and Sprint review require actual team input |
| #21, #23 | Grafana installation/import and end-to-end physical demonstration pending |
| #25 | At least 30 authorized labelled windows and measured quality still required |
| #29, #30 | Deployment, two reboot checks and second-member reproduction pending |
| #31, #32 | 60-minute acceptance, rehearsal and reviewed stable main required; no release created |
| #34 | PR #56 research included with the requested listening-coverage correction; needs review/integration |

No issue is closed merely because a branch contains partial implementation.

## Grafana draft provisioning (#21)

`dashboards/txori.json` and `deploy/grafana/provisioning/` provide a reproducible
SQLite dashboard draft. Environmental gaps stay null, light is raw, bird rows
are observations, and health includes age in seconds. The archive panel explicitly
shows coverage and does not claim current-day aggregates have been materialized.
Use `/summaries/daily` for current days until incremental materialization is added.

The SQLite plugin must be installed on ARM64 and Grafana's account given only
read access to the database/WAL. Copy the dashboard into the provisioned path
and the YAML into Grafana's provisioning directories. Import, SQL adapter syntax,
permissions, visual inspection and resource consumption are **not yet verified**
on Grafana. Do not treat the draft as completing #21 or the #23 demonstration.
