# Audio and data privacy

## Design principle

Local capture and inference on the Raspberry Pi. **Recordings of conversations are not stored and raw audio is not transmitted.** This is a constraint to be implemented and verified, not an already validated guarantee of non-existent software. There is no speaker recognition or transcription.

The decision and its system configuration are recorded in [ADR 0006](adr/0006-transient-audio.md); this page is the policy and the verification procedure ([#11](https://github.com/elenaatorralbo/txori-kantua/issues/11)).

## Allowed flow

Microphone → bounded window in RAM → inference → species/confidence/time metadata → removal of the reference to the window. The buffer is reused and its size is bounded; secure physical erasure of managed memory is not promised. There will be no temporary WAV files, audio spool, dumps or sample logging.

Bounds (ADR 0006): 3 s windows of 16-bit mono PCM at 48 kHz, at most two windows queued, at most 2 MB of audio in RAM in total, each window discarded after inference or after 10 s. When inference falls behind, the oldest window is dropped and counted; audio never accumulates.

## Where audio is forbidden

| Destination | Policy | Safeguard | How it is checked |
|---|---|---|---|
| Disk: any file, including `/tmp`, `/var/tmp`, `/dev/shm`, the data and application directories | Forbidden, also "only for debugging" | Audio units have no writable path; `PrivateTmp=yes` | `privacy.audit files` |
| Swap | Forbidden on disk; compressed RAM (zram) without writeback allowed | `deploy/privacy/90-txori-zram-only.conf` | `privacy.audit system` |
| Core dumps | Forbidden | `LimitCORE=0`; `deploy/privacy/90-txori-no-coredump.conf`; `fs.suid_dumpable=0` | `privacy.audit system [--pid]` |
| MQTT | Forbidden: contract fields only | JSON Schema with `additionalProperties: false` | `privacy.audit payloads --mqtt` |
| REST API | Forbidden: metadata from SQLite only | No audio column or endpoint in `contracts/openapi.yaml` | `privacy.audit payloads` on responses |
| Logs and journald | Forbidden: no buffers, arrays, base64 or file paths to audio | `txori_kantua.privacy.log_guard` installed in every audio process | `journalctl ... \| privacy.audit payloads` |
| Backups | Forbidden: database and configuration only ([ADR 0007](adr/0007-retention.md)) | Audio never reaches the database | `privacy.audit files` on the backup directory |
| Git repository | Forbidden | `.gitignore`; `tests/test_repository_has_no_audio.py` checks content, not only names | `pytest` |
| Network beyond the Pi | Forbidden | Inference is local; audio units only reach `localhost` | Traffic inspection (step 5 below) |

The provisioning test reviews swap and dumps so that pages containing audio cannot reach disk. On Raspberry Pi OS Trixie this matters: `rpi-swap` defaults to `zram+file`, which writes idle zram pages to `/var/swap` on the SD card. Do not assume that "using RAM" is enough. The policies are tested with synthetic sound and without recording people.

## Allowed data and minimisation

Candidate species, score, model version, observation/reception time, logical station, environmental values and technical health. Capture health may report numbers about the signal (level in dBFS, clipping ratio, dropped windows), never the signal. An approximate location for filtering may remain in local configuration; do not publish sensitive wildlife coordinates. Do not store voices, transcriptions, visitor identifiers or personal presence histories. PIR/touch trigger interaction, not profiles of people.

Retention proposed in ADR 007, pending capacity and team review. Purge and backup only of the necessary metadata. Credentials outside Git, rotated logs, minimal permissions and local access by default. A visible notice at the station will explain that it analyses sounds locally to detect birds and does not keep audio.

## Verification procedure

The audit tool is read-only, needs no extra dependencies and prints Markdown for the evidence report. Exit code 0 means nothing found, 1 means review needed. Run it on the Pi from the repository checkout or the installed virtual environment; use `sudo` for full coverage of system directories.

```bash
A="python -m txori_kantua.privacy.audit"

# 0. Install the system safeguards once, then reboot (ADR 0006).
sudo install -D -m 0644 deploy/privacy/90-txori-zram-only.conf /etc/rpi/swap.conf.d/90-txori-zram-only.conf
sudo install -D -m 0644 deploy/privacy/90-txori-no-coredump.conf /etc/systemd/coredump.conf.d/90-txori-no-coredump.conf
sudo reboot

# 1. Prove the procedure detects audio: plants a synthetic tone file and a
#    payload with base64 audio, expects both to be reported, removes its file.
$A control /var/lib/txori-kantua
$A control /tmp

# 2. Swap, zram writeback, core dumps, /tmp and journald.
$A system
$A system --pid "$(systemctl show -p MainPID --value <audio-service>)"   # once the service exists

# 3. Mark the start, run the capture or inference test, then list every file
#    created since the mark and any audio anywhere in the default paths.
date +%s > /run/user/$(id -u)/privacy-start
#    ... run the test (e.g. issue #7 ten windows, issue #8 benchmark) ...
sudo $A files --since "$(cat /run/user/$(id -u)/privacy-start)"

# 4. Every MQTT message while the test runs (with the broker of #13).
mosquitto_sub -h localhost -t 'txori/#' -v | $A payloads --mqtt

# 5. Logs of the test window, and outgoing connections of the audio processes.
journalctl --since "-15min" -o cat | $A payloads
sudo ss -tunp | grep -i python   # only localhost:1883 is expected
```

Authorised corpus files used by the benchmark of [#8](https://github.com/elenaatorralbo/txori-kantua/issues/8) can be excluded from step 3 by their recorded SHA-256 with `--allow-manifest <manifest.json>`; they are an external evaluation fixture, not audio captured by the station.

## Mandatory verification

1. Inventory every write path, temporary file, log, library cache, swap and dump: steps 2 and 3, plus a review of the service units.
2. Run capture/inference with authorised synthetic sound; review the files created and the data persisted: step 3.
3. Inspect MQTT publications and outgoing traffic in a test environment: only allowed metadata: steps 4 and 5.
4. Force disconnection, a full queue and an inference failure; check that no emergency recording mechanism appears: repeat step 3 after each.
5. Attach results and configuration to the issue, without personal audio, using [the report template](templates/issue-11-privacy.md). Repeat before MVP acceptance.

An authorised public corpus without voices can be used as an external evaluation fixture, with origin and licence recorded; this is not equivalent to keeping audio captured by the station. In case of accidental persistence or transmission, stop capture, limit access, delete the affected data according to the team procedure, fix and repeat the tests before restarting.

## Status

Tooling, tests and system drop-ins exist and were run on a laptop on 17/11/2026 (`pytest`, `privacy.audit control`, `privacy.audit system`). **Nothing has been verified on the Raspberry Pi yet**; the evidence of #11 is pending a session on the Pi.
