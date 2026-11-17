# 0006 — Keep audio transient and in RAM only

- **Status:** Proposed
- **Proposed on:** 17/11/2026
- **Owner:** David Fernández — [DavidFernandezUD](https://github.com/DavidFernandezUD)
- **Issue:** [#11](https://github.com/elenaatorralbo/txori-kantua/issues/11)
- **Accepted on:** —

## Context

The station listens continuously in a public space. People will talk near it.
[privacy.md](../privacy.md) promises that conversations are never stored and
raw audio is never transmitted. That promise has to hold from the first
capture test ([#7](https://github.com/elenaatorralbo/txori-kantua/issues/7)),
not only once the MVP is finished.

"We keep it in RAM" is not enough by itself. On Linux, process memory can
reach disk through swap, through zram writeback, and through core dumps. A
debug line can put samples into journald. A convenience `.wav` written to
`/tmp` "only while testing" is on the SD card. On the Pi this is concrete:
Raspberry Pi OS Trixie (Debian 13, the OS installed on 12/11/2026) uses
`rpi-swap`, whose default `Mechanism=auto` currently means **`zram+file`**:
idle zram pages are periodically written back to `/var/swap` on the SD card
(see `man swap.conf`). `provision.sh --disable-swap` targets
`dphys-swapfile`, which Trixie no longer ships, so its `swapoff -a` is undone
on the next boot.

Known for certain: BirdNET analyses 3 s windows at 48 kHz
([#8](https://github.com/elenaatorralbo/txori-kantua/issues/8)). Assumed until
measured: the window rate, the inference latency and the memory headroom.

## Decision

**Audio exists only as a bounded, reused buffer in the memory of the capture
and inference processes. It is never written to a file, a pipe to another
host, a message, a log or a backup, and the system is configured so that the
kernel cannot write those pages to disk either.**

### 1. The buffer

| Parameter | Value | Reason |
|---|---|---|
| Format | 16-bit signed PCM, mono, 48 000 Hz | BirdNET input rate; mono is enough for the model |
| Window | 3.0 s = 144 000 samples = 288 000 bytes (576 000 as float32) | BirdNET V2.4 segment length |
| Queue | At most **2 windows** waiting for inference | One being filled, one being analysed |
| Total audio in RAM | **≤ 2 MB** including the float32 copy given to the model | Fixed upper bound, independent of load |
| Lifetime | A window is discarded after inference **or after 10 s**, whichever is first | Never older than three windows |
| Overflow | If the queue is full, the **oldest window is dropped** and a counter increases | Losing audio is acceptable; accumulating it is not |
| Reuse | Buffers are pre-allocated and overwritten, not appended | Memory use stays flat; no growth on backlog |

Overwriting a buffer is not secure erasure: Python and NumPy may keep copies
in freed memory until the allocator reuses it. That is why section 3 makes
sure such memory cannot leave RAM, instead of promising erasure.

### 2. What may leave the process

Only the detection metadata of the contract: scientific name, score, window
start/end, model name and version (`contracts/mqtt/detection.schema.json`,
which already rejects any additional field). Capture health may publish
counts and levels (dropped windows, RMS in dBFS, clipping ratio): numbers
about the signal, never the signal.

| Channel | Rule | Enforced by |
|---|---|---|
| Disk (any path, including `/tmp`, `/dev/shm`, `/var/lib/txori-kantua`) | No audio file, ever; no "debug" WAV | Service unit with no writable path (`ProtectSystem=strict`, `PrivateTmp=yes`, no `ReadWritePaths`); `privacy.audit files` |
| MQTT | Contract fields only | JSON Schema `additionalProperties: false`; `privacy.audit payloads --mqtt` |
| REST API | Reads metadata from SQLite only; no audio column exists | `contracts/openapi.yaml`; review |
| Logs and journald | No buffers, arrays or base64 in log records | `txori_kantua.privacy.log_guard` filter; review |
| Backups | Database and configuration only ([ADR 0007](0007-retention.md)) | No audio ever reaches the database |
| Swap | Compressed RAM only, never a file or partition | `deploy/privacy/90-txori-zram-only.conf`; `privacy.audit system` |
| Core dumps | Disabled | `LimitCORE=0` in the unit, `deploy/privacy/90-txori-no-coredump.conf`, `fs.suid_dumpable=0` |
| Network | Capture and inference run on the Pi; no outbound audio connection | `IPAddressDeny=any` plus `IPAddressAllow=localhost` in the audio units (broker on the Pi); traffic inspection in the procedure |

### 3. System configuration on the Pi

1. `rpi-swap` with `Mechanism=zram` (RAM only, no writeback file). If the
   BirdNET measurement shows that the inference process fits with margin and
   no swap, `Mechanism=none` is the stricter option. Never `zram+file` or
   `swapfile`.
2. systemd-coredump with `Storage=none`; every audio unit with `LimitCORE=0`.
3. Audio services hardened like the existing station unit: unprivileged user,
   `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp=yes`,
   `MemorySwapMax=0`, `DevicePolicy=closed` with only the sound device
   allowed, and **no writable path**: a bug that tries to write a WAV fails
   with a read-only filesystem error instead of leaking.
4. Optionally `mlock` the buffers. Not required while swap is RAM-only; it
   becomes required if anyone proposes disk swap again.

## Alternatives considered

| Alternative | For | Against | Why it is not chosen now |
|---|---|---|---|
| Write short WAV files to a tmpfs and delete them | Simple with command-line tools; BirdNET-Analyzer works on files | A file is a file: other processes, backups and crash leftovers can see it; tmpfs pages can swap | It makes "no audio on disk" depend on cleanup code always running |
| Keep a rolling archive "for model quality review" | Would allow re-analysing false positives | Directly contradicts the privacy promise; would store conversations | Forbidden by privacy.md, not a trade-off |
| Disable swap entirely (`Mechanism=none`) | Strongest guarantee | Less headroom for BirdNET and Grafana; the Pi's RAM size is not yet recorded in the inventory (#1) | Kept as the fallback once #8 measures real memory |
| Secure erasure of buffers (zeroing on release) | Feels safer | Not achievable for Python/NumPy temporaries; gives false assurance | Prevent persistence at the OS level instead |

## Consequences

- Capture ([#15](https://github.com/elenaatorralbo/txori-kantua/issues/15))
  and inference ([#16](https://github.com/elenaatorralbo/txori-kantua/issues/16))
  must work on in-memory arrays; tools that only accept file paths are
  excluded or wrapped.
- Debugging recognition quality cannot use station recordings. It uses the
  authorised public corpus of #8 and
  [#25](https://github.com/elenaatorralbo/txori-kantua/issues/25).
- Provisioning needs the two drop-ins in `deploy/privacy/`. Javier's
  `provision.sh --disable-swap` should be updated for `rpi-swap` (follow-up
  for [#2](https://github.com/elenaatorralbo/txori-kantua/issues/2)).
- The privacy audit becomes part of every acceptance run (see
  [acceptance.md](../acceptance.md), Privacy gate).

## Review criteria

- Measured inference memory (#8) leaves less than 512 MB free with
  `Mechanism=zram`: reconsider the window queue or move other services away,
  never enable disk swap.
- Any audit finding of audio on disk, in a payload or in a log: stop capture,
  follow the incident steps in privacy.md, and amend this ADR.
- A future requirement to keep audio for any purpose needs a new ADR, consent
  and a privacy review; it cannot be added by editing this one.

## Evidence

Pending, produced in [#11](https://github.com/elenaatorralbo/txori-kantua/issues/11)
and [#7](https://github.com/elenaatorralbo/txori-kantua/issues/7) on the Pi:

- `python -m txori_kantua.privacy.audit control DIR` passes on the Pi.
- `privacy.audit system` reports no FAIL after installing the drop-ins and
  rebooting.
- `privacy.audit files --since ...` reports no audio after the ten-window
  capture of #7 and after the BirdNET benchmark of #8.

Verified off the Pi on 17/11/2026: the audit and its tests run on a laptop
(Debian 12, Python 3.11). That checks the tooling, not the station.
