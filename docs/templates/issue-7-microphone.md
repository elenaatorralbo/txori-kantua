# Issue #7 — USB microphone report template

**Template only — not executed.** `mic_check` generates most of the report (see [audio-capture.md](../audio-capture.md)); save its output to `docs/evidence/YYYY-MM-DD-issue-7-capture.md` and `...-disconnect.md` with the actual session date, then complete this checklist in the same PR. Never attach audio.

- **Run by:** PENDING
- **Reviewed by:** PENDING
- **Microphone and USB interface (model, revision):** PENDING
- **Where it was plugged in (Pi USB port, hub):** PENDING
- **Test sound (source, frequency, level, distance):** PENDING
- **Room and background noise:** PENDING

## Runs

| Run | Command | Report file | Exit code |
|---|---|---|---|
| Device list | `mic_check --list` | PENDING | PENDING |
| Tone, 10 windows | `mic_check --expect-tone 1000` | PENDING | PENDING |
| Silence, 10 windows | `mic_check` | PENDING | PENDING |
| Loud sound (clipping) | `mic_check --windows 3` | PENDING | PENDING |
| Disconnection and reconnection | `mic_check --disconnect-test --reconnect-wait 60` | PENDING | PENDING |

## Acceptance

- [ ] The report identifies device, channels, rate and test duration.
- [ ] Ten consecutive windows were captured without error and without persistent audio files.
- [ ] Disconnection was detected and the application did not block indefinitely.
- [ ] Observed clipping/silence behaviour noted, with the gain setting used.
