# Pipeline verification — 17 November 2026

Integration branch: `feature/remaining-issues`. Results below apply to the
implementation committed with this report, except where an earlier snapshot is
explicitly identified. No release or full physical acceptance is asserted.

## Software suite

- macOS arm64, Python 3.14: `python -m pytest -q` — **525 passed, 9 skipped**.
  Eight live-broker tests and the actual-model test are opt-in.
- Raspberry Pi 5, Debian 13 arm64, Python 3.13.5: same suite from a source copy —
  **524 passed, 10 skipped**. The extra skip is the Git-tracked-audio check: the
  temporary copy is not a Git checkout; that check ran on the Mac.
- `git diff --check`: passed.
- API responses checked against the committed OpenAPI, including missing storage,
  invalid ranges/cursors, pagination, empty results, failed environmental readings
  and sanitized internal errors.
- Storage checks cover duplicate UUIDs, conflicting UUID content, reopening,
  consistent backup/restore, read-only access, projection-before-purge and late
  correction rejection after archival.
- Input tests cover PIR/touch logical timeout, debounce, stale events and MQTT
  disconnection. These are not physical sensor measurements.

An initial Pi copy omitted `deploy/privacy`; its two fixture-dependent tests
failed with FileNotFoundError. The complete tree was copied and the suite rerun
successfully, as recorded above. No application defect was hidden by those errors.

## Real isolated MQTT transport on the Pi

Mosquitto **2.0.21** (Debian arm64 packages extracted into a temporary directory,
not installed as a system service); paho-mqtt **2.2.0**; Flask **3.1.3**.
Broker binds only to loopback on a random port and uses generated temporary
credentials plus the repository ACL. No production broker configuration changed.

Command:

```bash
LD_LIBRARY_PATH=/tmp/txori-broker-review/root/usr/lib/aarch64-linux-gnu \
PYTHONPATH=src /tmp/txori-issues-venv/bin/python tools/verify_pipeline.py \
  --mosquitto /tmp/txori-broker-review/root/usr/sbin/mosquitto \
  --passwd /tmp/txori-broker-review/root/usr/bin/mosquitto_passwd
```

The earlier verifier snapshot restarted the broker immediately. At
**2026-11-17T17:47:28.807Z**, it reported:

```json
{"broker_restart":"PASS","consumer":{"duplicates":9,"inserted":10},"input":"synthetic metadata; no audio","lcd_consumer_deliveries":4,"result":"PASS","stored_detections":1}
```

`inserted` includes availability messages from several test clients; it is not a
bird count. Three sends of the same detection produce one stored detection;
the station subscriber independently receives it. A resend queued during the
broker outage keeps its original ID/time and does not increase the stored count.

The live broker suite reported **7 passed, 1 skipped**. It exercises authorized
publication, anonymous rejection, forbidden-topic writes, Last Will and bounded
queues. Its system-service restart test is skipped; the standalone harness tests
its own temporary broker restart instead.

The final verifier extends the outage to **60 seconds by default**. On its Pi
run, the full suite and seven broker checks passed, but SSH/name resolution was
lost before the final result could be retrieved. **The 60-second result is not
claimed here.** It is rerunnable through the new CI integration job.

## Installed-layout health check

A separate `/tmp/txori-layout-check` mirrored `app/` and `venv/`, with an editable
installation and `TXORI_CONTRACTS_DIR=.../app/contracts/mqtt`. From working
directory `/`, the venv interpreter successfully ran `health.monitor --once`.
At 17:49:32 UTC it emitted a contract event and correctly reported the deliberately
stopped station as `failed` (`inactive/dead`). This validates imports and contract
resolution outside the source directory; it does not claim the new systemd unit
was installed or its DynamicUser/resource limits were exercised.

## Operator observations and remaining hardware work

Elena confirmed two complete 16-character LCD rows and the transliterated name
`Herrerillo comun`, with `Cyanistes caerul` on the second row. Photo/video and
long-name pagination acceptance remain pending. The installed JHD1802 driver's
`_backlight_on` method is a no-op: physical timeout is not verified.

Elena identified PIR on D16 and confirmed no touch connected. A USB microphone
was detected, but capture was not started: zram has disk writeback to `/var/swap`
and Elena later said she could not perform the audio check at that time.

The existing station and timer were stopped by Elena for LCD testing. Their last
observed state was inactive. No privileged service restart was performed by this
session; restoring them requires access to the Pi and sudo. The new software
remains in a temporary test copy, not deployed over the existing station.
