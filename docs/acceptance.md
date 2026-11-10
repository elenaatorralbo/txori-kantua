# Acceptance evidence

No check is passed by creating this document. Link results in the corresponding issues and review them with another member.

| Gate | Minimum evidence | Blocks |
|---|---|---|
| Foundations | Real inventory, Pi/Grove, sensors, LCD, USB; versions and dated tests | Sprint 1 closure |
| AI feasibility | Authorised corpus, p50/p95, RAM/CPU/temperature and decision | Commitment to the AI pipeline |
| Pipeline | Three physical changes traced by ID from sensor to dashboard, with persistence | 03/12 review |
| Contracts | Valid and invalid examples, units, versions and duplicates | Integration |
| Interaction | PIR/touch, ES/EU/EN, expired events and switch-off at 20 ±1 s | MVP acceptance |
| Reliability | 60 s broker outage, DB down, missing sensor and two full reboots | MVP acceptance |
| Privacy | Audit of disk/persistent memory, payloads and traffic without audio | All capture and release |
| Delivery | 60 min rehearsal, CI, installation by another member and reviewed PRs | `v1.0.0` |

Logic tests use pytest and hardware doubles; physical tests are reproducible manual tests. Only tables, sanitised logs, metrics and photos/video that do not reveal people or sensitive information will be kept. All evidence states date, commit, hardware, versions, conditions, result and limits.

Proposed script (5–7 minutes): purpose/privacy, environmental change through to the dashboard, bird detection with a clearly identified authorised corpus if no birds are present, LCD interaction, failure/recovery and limits. The contingency does not replace physical tests already required. Each member must explain an interface they did not implement personally.
