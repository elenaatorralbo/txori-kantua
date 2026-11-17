# Sprint 1 review — 17/11/2026

Issue [#12](https://github.com/elenaatorralbo/txori-kantua/issues/12).
Prepared by David (Scrum Master) on the morning of 17/11/2026 from the GitHub
state at that time. Sections marked **PENDING** are filled in during the
meeting; nothing in them is decided in advance. This document does not mark
any hardware as tested.

- **Date and place:** 17/11/2026, PENDING
- **Attendees:** PENDING
- **Minutes taken by:** PENDING
- **Sprint goal:** reduce hardware risks, fix contracts and prepare integration ([scrum.md](scrum.md)).

## Agenda (about 45 minutes)

1. Sprint goal and status of the twelve Sprint 1 issues (10 min).
2. Demonstrations: only what runs, on whatever it runs; say where (10 min).
3. Decisions: ADRs, the status of #2, carry-over (10 min).
4. Capacity of each person and Sprint 2 commitment (10 min).
5. Retrospective: one improvement, owner and follow-up (5 min).

## 1. Status of Sprint 1

GitHub state on 17/11/2026 before the meeting: milestone *Sprint 1 —
Foundations* with **3 issues closed and 9 open**. "Hardware evidence" means a
dated report from the Raspberry Pi in `docs/evidence/`.

| Issue | Owner | GitHub | What exists | Hardware evidence | Pending to close |
|---|---|---|---|---|---|
| [#1](https://github.com/elenaatorralbo/txori-kantua/issues/1) Inventory and safe wiring | Elena | Open | Session guide and report template ([PR #44](https://github.com/elenaatorralbo/txori-kantua/pull/44)) | None in `docs/evidence/` | Completed inventory report, wiring review |
| [#2](https://github.com/elenaatorralbo/txori-kantua/issues/2) Pi OS and Python environment | Javier | **Closed 11/11** by merging [PR #40](https://github.com/elenaatorralbo/txori-kantua/pull/40) | Provisioning scripts and procedure | [provisioning.md](provisioning.md) says "not run on hardware"; no `collect_report.sh` report | **Decision needed** (section 3) |
| [#3](https://github.com/elenaatorralbo/txori-kantua/issues/3) Grove Base Hat and buses | Elena | Open | Template | Partial: [12/11 recovery](evidence/2026-11-12-recovery/validation.md) shows I2C LCD and GPIO DHT11 working | Bus/address record, driver versions |
| [#4](https://github.com/elenaatorralbo/txori-kantua/issues/4) Temperature, humidity, pressure, light | Erik | Open | DHT11 driver in `src/` | Partial: DHT11 real readings on 12/11 | Pressure and light; 30 readings per channel |
| [#5](https://github.com/elenaatorralbo/txori-kantua/issues/5) PIR and touch | Elena | Open | Debounce and presence logic with synthetic tests ([PR #43](https://github.com/elenaatorralbo/txori-kantua/pull/43)) | None | Ten physical cycles per input |
| [#6](https://github.com/elenaatorralbo/txori-kantua/issues/6) Grove RGB LCD | Elena | Open | Text formatter ([PR #42](https://github.com/elenaatorralbo/txori-kantua/pull/42)) | Partial: LCD writing on 12/11 | Character, colour, backlight and restart tests |
| [#7](https://github.com/elenaatorralbo/txori-kantua/issues/7) USB microphone | David | Open | `mic_check` tool, tests, procedure; desktop run with a real USB interface (branch `feature/7-usb-microphone-capture`) | None | Run on the Pi with the team's microphone |
| [#8](https://github.com/elenaatorralbo/txori-kantua/issues/8) BirdNET feasibility | David | Open | Wrapper, benchmark, corpus, ADR 0001; desktop run with the real models (branch `feature/8-birdnet-feasibility`) | None | Benchmark, sustained and live runs on the Pi; decision in ADR 0001 |
| [#9](https://github.com/elenaatorralbo/txori-kantua/issues/9) Architecture and MVP boundaries | Javier | Closed 11/11 ([PR #38](https://github.com/elenaatorralbo/txori-kantua/pull/38)) | MVP scope, interface registry, ADRs 0002–0004 and 0007 | Not applicable | ADRs still **Proposed**: team approval |
| [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10) MQTT and REST contracts | Javier | Closed 11/11 ([PR #39](https://github.com/elenaatorralbo/txori-kantua/pull/39)) | JSON Schemas, OpenAPI, examples and contract tests | Not applicable | Team review before producers integrate |
| [#11](https://github.com/elenaatorralbo/txori-kantua/issues/11) Audio privacy | David | Open | Policy, ADR 0006, audit tool, drop-ins (branch `feature/11-audio-privacy-safeguards`) | None | Audit on the Pi after installing the drop-ins |
| [#12](https://github.com/elenaatorralbo/txori-kantua/issues/12) Sprint review and capacity | David | Open | This document | Not applicable | Minutes, capacity and commitment below |

### Against the sprint goal

| Part of the goal | Assessment before the meeting |
|---|---|
| Fix contracts | **Met**: contracts, examples and tests merged (#10); the LCD formatter already consumes the detection contract ([review](lcd-contract-review.md)) |
| Prepare integration | **Mostly met**: architecture, MVP scope and interface owners agreed in writing (#9); privacy policy and capture/inference tooling ready for review (#7, #8, #11) |
| Reduce hardware risks | **Partly met**: the Pi was recovered and runs DHT11 + LCD with bounded startup (12/11). No inventory, Hat, PIR/touch, microphone or BirdNET evidence yet |

Roadmap rule: "absence does not equal a passed test". The open hardware
issues are carried over with their blocker and next action (section 3), not
closed.

## 2. What can be demonstrated

| Item | Where it runs | Command |
|---|---|---|
| Contract validation, LCD formatting, touch/PIR logic | Any laptop | `pytest` |
| Station recovery (DHT11 + LCD, watchdog, disable flag) | The Pi | [raspberry-recovery.md](raspberry-recovery.md) |
| Privacy audit with planted control file and payload | Any Linux machine | `python -m txori_kantua.privacy.audit control /tmp` |
| Microphone capture into RAM, 10 windows, absent-device handling | Laptop with a USB interface; Pi pending | `python -m txori_kantua.audio.mic_check` |
| BirdNET on the five-recording corpus, three precisions | Laptop; Pi pending | `python -m txori_kantua.audio.benchmark run ...` |

Desktop results are shown as such. They do not replace the Pi runs.

## 3. Decisions for the meeting

| # | Question | Options | Decision |
|---|---|---|---|
| D1 | Status of the Proposed ADRs 0001, 0002, 0003, 0004, 0006, 0007 | Accept now / accept with changes / keep Proposed until evidence | PENDING |
| D2 | #2 was closed by the PR merge, but its own document says its criteria are pending hardware | Reopen #2 until the `collect_report.sh` report exists / keep closed and record the evidence as a follow-up | PENDING |
| D3 | Sprint 1 hardware issues not closed today (#1, #3, #4, #5, #6, #7, #8, #11) | Carry over to Sprint 2 as the first priority, with the Pi schedule below | PENDING |
| D4 | `provision.sh --disable-swap` targets `dphys-swapfile`, which Trixie no longer has; the default `rpi-swap` mode writes zram pages to the SD card (ADR 0006) | Javier updates #2's script / David's drop-in in `deploy/privacy/` is enough | PENDING |
| D5 | Who reviews each open PR (main requires one approval from another member) | One named reviewer per PR | PENDING |

### One Raspberry Pi for four people

There is a single Pi. Physical tests can only happen one after another, which
is now the main schedule risk. Proposed order for the first days of Sprint 2,
following the hardware dependencies of the [roadmap](roadmap.md):

| Slot | Owner | Issues | Needs | Notes |
|---|---|---|---|---|
| 1 | Elena (+ reviewer) | #1, #3 | Pi, Hat, all Grove parts, camera | Inventory and buses first: everything else depends on them |
| 2 | Elena, Erik | #4, #5, #6 | Pi with Hat and sensors | Can share one session |
| 3 | David | #11, #7 | Pi, USB microphone, a phone for the test tone | Drop-ins need one reboot; does not touch GPIO/I2C |
| 4 | David | #8 | Pi with its usual case and cooling, ~1 h | The sustained run heats the CPU: do not measure temperature-sensitive sensors at the same time |
| 5 | Javier | #2 report, #13 | Pi, network | If D2 reopens #2 |

Dates and times: PENDING (agree in the meeting). Whoever holds the Pi posts
in the team channel when it is free, and nobody reflashes it without warning
the others ([sprint1-hardware-session.md](sprint1-hardware-session.md)).

## 4. Capacity and Sprint 2 commitment

Sprint 2 runs 17/11–03/12 (review on 03/12). Each person states their own
availability; nothing is assumed for them. Points are relative estimates, not
hours ([scrum.md](scrum.md)).

| Person | Available hours per week | Days not available | Sprint 1 carry-over | New Sprint 2 issues proposed | Proposed points | Commitment agreed |
|---|---|---|---|---|---|---|
| David | PENDING | PENDING | Pi runs of #7, #8, #11 | #15, #16, #17 | 13 | PENDING |
| Javier | PENDING | PENDING | #2 report if reopened | #13, #18, #19, #20 | 16 | PENDING |
| Elena | PENDING | PENDING | #1, #3, #5, #6 | #14, #22 | 10 | PENDING |
| Erik | PENDING | PENDING | #4 | #21, #23, #24 | 11 | PENDING |

The proposed points come from [backlog.md](backlog.md) and do not include the
carry-over. If capacity is lower than the load, cut in the order of
[mvp-scope.md](mvp-scope.md) ("What is cut first") and record the cut here;
never cut privacy verification, the sensor → dashboard flow, reboot
recovery or deduplication.

## 5. Risks after Sprint 1

| Risk | Change since planning | Response | Owner |
|---|---|---|---|
| Single Pi shared by four people | New: physical tests serialise | Slot schedule above; group tests that use the same wiring | David |
| Hardware not evidenced by 17/11 | Most hardware issues open | Carry over first in Sprint 2; no "Done" without a report | Each owner |
| BirdNET too slow or hot on the Pi | Runtime risk reduced: `ai-edge-litert` has Python 3.13 aarch64 wheels and the models work through our wrapper (desktop). Pi numbers unknown | Benchmark in slot 4; fallbacks in ADR 0001 | David |
| Audio pages reaching the SD card | New: Trixie's default `rpi-swap` uses zram writeback to `/var/swap` | Drop-in `Mechanism=zram`; audit after reboot (D4) | David, Javier |
| BirdNET false positives for local birds | New: a blackbird recording produced an Australian species on desktop | Location/season filter (#17) is not optional; show scores as scores | David |
| No Basque common names in BirdNET labels | New: the archive has Spanish and English but not Basque | EU names from another reviewed source for #22 | Elena |
| Issues closed before their hardware criteria | New: #2 | D2; close issues manually after evidence instead of `Closes #N` when hardware is pending | Team |

## 6. Retrospective

| What went well | What to improve | Action, owner, follow-up date |
|---|---|---|
| PENDING | PENDING | PENDING |

## Links

[Architecture](architecture.md) · [MVP scope](mvp-scope.md) ·
[Interface registry](interfaces.md) · [ADRs](adr/README.md) ·
[Hardware plan](hardware.md) · [Sprint 1 hardware session](sprint1-hardware-session.md) ·
[Evidence](evidence/README.md) · [Backlog](backlog.md) ·
[Project board](https://github.com/users/elenaatorralbo/projects/2) ·
[Milestone Sprint 1](https://github.com/elenaatorralbo/txori-kantua/milestone/1)
