# Issue #6 — physical test report template

**Template only — not executed.** Copy to `docs/evidence/YYYY-MM-DD-issue-6-description.md` using the actual session date. Replace PENDING with observations; an unchecked criterion is not a pass.

- **Date (UTC):** PENDING
- **Run by:** PENDING
- **Reviewed by:** PENDING
- **Issue / PR:** #6 / PENDING
- **Commit:** PENDING
- **Hardware:** PENDING (exact model, OS, architecture)
- **Relevant versions:** PENDING (Python, drivers, libraries)
- **Procedure:** [Session guide](../sprint1-hardware-session.md); exact commands: PENDING
- **Expected result:** See checks below.
- **Observed result:** PENDING
- **Limitations and pending tests:** PENDING

## Setup

- Grove #3 report: PENDING
- LCD model/revision/port/address: PENDING
- Driver version, script and command: PENDING
- Formatter commit (if used): PENDING
- Character policy and physical ROM observations: PENDING

| Check | Input / expected behaviour | Observed result | Photo/video/log |
|---|---|---|---|
| Two full rows | Row 1: `1234567890ABCDEF`; row 2: `abcdefghijklmnop` | PENDING | PENDING |
| Accented name | `Herrerillo común`; ASCII policy displays `Herrerillo comun` | PENDING | PENDING |
| Long name / pages | `Carbonero común / Parus major / Great tit`; all text readable across pages | PENDING | PENDING |
| Overwrite | Long text then `Blue tit`; no stale trailing characters | PENDING | PENDING |
| Colours | Red, green and blue requested through the model's driver | PENDING | PENDING |
| Backlight off | Backlight visibly switches off | PENDING | PENDING |
| Restart test | Stop/start test process; both lines display correctly again | PENDING | PENDING |

- Actual page order and manual navigation procedure: PENDING
- Policy for unsupported characters and long names verified on display: PENDING
- Additional power-cycle test, if performed: PENDING

## Acceptance

- [ ] Photo/video shows two lines of up to 16 characters.
- [ ] Long and accented names follow the documented display policy.
- [ ] Screen recovers after restarting the test.
