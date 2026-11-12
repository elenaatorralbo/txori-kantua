# Issue #5 — physical test report template

**Template only — not executed.** Copy to `docs/evidence/YYYY-MM-DD-issue-5-description.md` using the actual session date. Replace PENDING with observations; an unchecked criterion is not a pass.

- **Date (UTC):** PENDING
- **Run by:** PENDING
- **Reviewed by:** PENDING
- **Issue / PR:** #5 / PENDING
- **Commit:** PENDING
- **Hardware:** PENDING (exact model, OS, architecture)
- **Relevant versions:** PENDING (Python, drivers, libraries)
- **Procedure:** [Session guide](../sprint1-hardware-session.md); exact commands: PENDING
- **Expected result:** See checks below.
- **Observed result:** PENDING
- **Limitations and pending tests:** PENDING

## Setup

- Grove #3 report: PENDING
- PIR model/port/active level: PENDING
- Touch model/port/active level: PENDING
- Adapter script and exact invocation: PENDING
- PIR measured warmup and configured stabilization: PENDING
- Touch debounce interval and measurement rationale: PENDING
- Polling interval and timestamp source: PENDING

## Ten real cycles per input

Use one table for PIR and one for touch. Record elapsed times for transitions
and link raw timestamped samples. An action count of one is expected per valid
cycle; record failures rather than replacing them with expected values.

### PIR

| Cycle | UTC start | Asserted at (ms) | Released at (ms) | Action count | Result / evidence |
|---|---|---|---|---|---|
| 1 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 2 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 3 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 4 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 5 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 6 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 7 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 8 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 9 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 10 | PENDING | PENDING | PENDING | PENDING | PENDING |

### Touch

| Cycle | UTC start | Asserted at (ms) | Released at (ms) | Action count | Result / evidence |
|---|---|---|---|---|---|
| 1 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 2 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 3 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 4 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 5 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 6 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 7 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 8 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 9 | PENDING | PENDING | PENDING | PENDING | PENDING |
| 10 | PENDING | PENDING | PENDING | PENDING | PENDING |



## Fault observations

| Check | Procedure/duration | Expected | Observed | Evidence |
|---|---|---|---|---|
| Sustained PIR presence | PENDING | No repeated activation while presence stays asserted | PENDING | PENDING |
| Held touch | PENDING | One action until release and new press | PENDING | PENDING |
| Idle false triggers | PENDING | Record count and duration | PENDING | PENDING |
| PIR disconnected | PENDING | Record behaviour; detection capability unverified | PENDING | PENDING |
| Touch disconnected | PENDING | Record behaviour; detection capability unverified | PENDING | PENDING |

## Acceptance

- [ ] Ten cycles per input have observed results and timestamps.
- [ ] Selected debounce produces no duplicate actions for a single touch.
- [ ] False triggers and disconnected behaviour documented.
