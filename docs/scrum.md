# SCRUM and collaboration

## Academic framework

The project accounts for 65 % of the course. Only the official **three-sprint** schedule is used. Administrative start: 03/11/2026; this preparation begins on 05/11, so no completed work is attributed to the previous days.

| Sprint | Interval | Review / delivery | Sprint Goal |
|---|---|---|---|
| 1 — Foundations | 03/11–17/11 | 17/11 | Reduce hardware risks, fix contracts and prepare integration |
| 2 — Working Pipeline | 17/11–03/12 | 03/12 | Show a physical sensor through to a dashboard with persisted data |
| 3 — MVP Release | 03/12–11/12 | Delivery 11/12 | Integrate birds, interaction, data and recovery with evidence |

Shared dates are review and transition days, not two days of capacity. In Projects, iterations are modelled as [start, next start); the review closure is kept in milestones and Target date. Final demonstration during the week of 14/12, without treating that week as additional development time.

## Team and accounts

| Person | Proposed responsibility | Verified account | Initial assignment |
|---|---|---|---|
| David Fernández | Scrum Master; audio and BirdNET; quality support | `DavidFernandezUD`, profile David Fernández Fernández and write access | Audio, AI, coordination and testing |
| Javier Santamaría | Product Owner; MQTT, API and data; provisioning | `javiers2004`, profile Javier Santamaría Pascual; access verified | Ten issues assigned to javiers2004; Owner = Javier |
| Elena Torralbo | Interaction sensors, LCD and experience | `elenaatorralbo`, profile Elena Torralbo and admin | Hardware, station and documentation |
| Erik Eguskiza | Dashboard, open data and monitoring | `eeguskiza`, profile Erik Eguskiza Aranda and write | Environmental sensors, dashboard, observability and reproduction |

Initial verification through profiles and collaborators on 05/11/2026; Javier was verified through his profile and invitation on 06/11/2026. `dieguich` is not Javier's identified account: no tasks are assigned to it and its permissions are not changed. Responsibilities are proposals, not confirmed availability commitments.

**Group confirmed by Elena on 06/11/2026:** the team of four is kept. The 2–3 requirement of the brief is kept as background; the recorded confirmation comes from the team, without inventing minutes or a reply from the lecturer. Net capacity per person still has to be confirmed in planning.

## Working rhythm

- Planning at the start: confirm net capacity, dependencies and criteria; select a realistic commitment.
- Short daily (10 minutes, synchronous or written): progress, next step and blocker. Escalate hardware blockers the same day.
- Refinement twice a week: prioritise by value/risk, clarify criteria and update estimates.
- Review on 17/11 and 03/12; final acceptance on 11/12: show behaviour and evidence, not just slides.
- Retrospective after each review: one concrete improvement, an owner and follow-up.

Initial estimates of 3 or 5 points are relative and must be reviewed; they are not hours or a historical velocity. Split an issue only if the deliverable turns out to be unmanageable; keep criteria and dependencies when splitting. The dashboard and persistence can start with clearly labelled fixtures, but only physical data meets the Sprint 2 review.

## Board and policies

`Backlog → To do → In progress → Review → Done`.

- Backlog: identified work, with no commitment to immediate execution.
- To do: selected in planning, dependencies and material available.
- In progress: one active issue per person as a target; occasional collaboration allowed.
- Review: PR open with tests and criteria met, review by another member.
- Done: criteria verified, documentation up to date and PR merged. Close an issue only with evidence.

The 34 new issues are created in **Backlog**. The **Owner** field identifies the planned owner even if their access is pending; **Assignees** keeps the effective GitHub assignment. The Javier view filters `owner:Javier` and shows his ten tasks. Milestone and iteration indicate forecast, not execution status. Blockers are recorded with cause, dependency and next action; Done is not marked to improve metrics.

## Definition of Ready / Done

Ready: purpose, proposed owner, verifiable criteria, necessary contracts, dependencies and discussed estimate. Done: functional scope (or a documented decision for research tasks), review by another member, tests with evidence, up-to-date documentation and merged PR. Physical infrastructure requires hardware evidence; simulated tests do not replace it.

Tracking: progress by criteria and goals, blocked work, time in Review and risks. Do not compare personal productivity by number of commits or points. Each member uses their own account and understands the whole architecture.
