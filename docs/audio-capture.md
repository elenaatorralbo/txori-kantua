# USB microphone capture

Procedure of issue [#7](https://github.com/elenaatorralbo/txori-kantua/issues/7).
It depends on [#2](https://github.com/elenaatorralbo/txori-kantua/issues/2)
(a working Pi environment) and [#11](https://github.com/elenaatorralbo/txori-kantua/issues/11)
(privacy safeguards, [ADR 0006](adr/0006-transient-audio.md)).

> **Status: not run on the Raspberry Pi.** The code was tested with fake
> capture processes and on a laptop with a real USB audio interface (see
> [Off-Pi verification](#off-pi-verification)). No acceptance criterion of #7
> is met until the report below is produced on the Pi with the team's
> microphone.

## How capture works

`arecord` (alsa-utils) writes raw 16-bit PCM to a pipe; Python reads it
straight into one pre-allocated 288 000-byte buffer (3 s at 48 kHz, mono) that
is overwritten for every window. There is no WAV header, file, spool or
temporary path at any point. Only level statistics leave the buffer.

| Concern | Behaviour |
|---|---|
| Stable device identity | ALSA name by card id, `hw:CARD=<id>,DEV=0`, not by card number; USB vendor:product id recorded |
| Supported formats | Read from `/proc/asound/cardN/stream0` without opening the device |
| Format conversion | `hw:` when the hardware supports 48 kHz mono S16 natively; otherwise `plughw:` and the report says ALSA converts |
| Disconnection | `arecord` exits (`No such device`) → `DeviceUnavailable`; if it hangs instead, no bytes for `--stall-timeout` (2 s) → `CaptureStalled` and the process is killed. The application never blocks indefinitely |
| Overruns | Counted from arecord's messages and reported |
| Clipping, silence, DC offset | Per window: peak and RMS in dBFS, % of clipped samples, DC offset; RMS below −60 dBFS is flagged as silent |
| Test tone check | `--expect-tone F` compares a zero-crossing estimate with F (±5 %) |

## Running it on the Pi

Requirements: Raspberry Pi OS with `alsa-utils` (installed by default) and the
repository with its virtual environment (see [provisioning](provisioning.md)).
Run as your personal user, which is in the `audio` group by default. The
future capture service ([#15](https://github.com/elenaatorralbo/txori-kantua/issues/15))
will need `txori` added to `audio`; that is not done here.

```bash
M="python -m txori_kantua.audio.mic_check"

# 1. Identify the device and its native formats.
arecord -l
$M --list

# 2. Ten consecutive 3 s windows with a test sound. Play a steady 1 kHz tone
#    from a phone about 30 cm from the microphone (any tone generator app),
#    then repeat once in silence and once with a loud clap to see clipping.
$M --expect-tone 1000 > docs/evidence/YYYY-MM-DD-issue-7-capture.md

# 3. Disconnection: unplug the USB interface when prompted, plug it back in
#    when prompted again.
$M --disconnect-test --reconnect-wait 60 > docs/evidence/YYYY-MM-DD-issue-7-disconnect.md
```

If several USB capture devices are present, choose one with
`--device hw:CARD=<id>,DEV=0` (from `--list`). Use `sudo` only if the report
says the file scan had unreadable entries and you want full coverage; the
capture itself does not need root.

Each report contains the evidence header of [evidence/README.md](evidence/README.md),
the device table, one row per window and a result table. The command exits
with 0 only if every check passed. Complete the "To fill in by hand" section
(microphone model, test sound, room) and review the report before committing
it: it contains no audio, IP addresses or names.

## Mapping to the acceptance criteria

| Criterion of #7 | How it is checked | Status |
|---|---|---|
| Report identifies device, channels, rate and test duration | Device and Configuration sections of the report | Tool ready; Pi report pending |
| Ten consecutive windows captured without error or persistent audio files | Windows section (10/10) and the issue #11 file scan of everything created during the run | Tool ready; Pi report pending |
| Disconnection is detected and does not block the application indefinitely | `--disconnect-test`: error type, time the failing read took (bound: window + stall timeout + 1 s), reopening while absent fails promptly, optional reconnection | Tool ready; Pi report pending |

## Off-Pi verification

17/11/2026, laptop with Debian 12 x86_64, Python 3.11.2, alsa-utils 1.2.8,
Focusrite Scarlett 2i2 USB (1235:8210, native S32_LE stereo only), nothing
connected to its inputs. **This checks the tool, not the station's
microphone, and does not satisfy #7.**

- `pytest tests/audio`: device parsing, window geometry, ten windows from a
  fake process, unplug mid-window, stalled process killed within the
  timeout, overrun counting, statistics of synthetic tones, full report.
- 10 windows through `plughw` at 48 kHz mono S16: 10/10, 30.17 s wall time
  for 30 s of audio, 0 overruns, RMS −68 dBFS (noise floor, flagged silent),
  no file created.
- 3 windows in the native format (`hw`, S32_LE stereo): 3/3.
- Absent device (`hw:CARD=Nope,DEV=0`): failed in 0.07 s with
  `audio open error: No such device`.
- Not tested: physically unplugging the interface during capture.

## Known limitations

- The zero-crossing frequency estimate only means something for a clean
  tone; with birdsong or noise it is just a number.
- `/proc/asound/cardN/stream0` exists for USB audio class devices only. Other
  devices still work with `--device`, but the format table is empty.
- An unplug that the kernel does not report (a broken cable that still
  enumerates) shows up as silence, not as an error. The silence flag is the
  only signal for that case.
