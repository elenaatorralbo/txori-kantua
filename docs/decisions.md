# Initial technical decision record

One-line index per decision. The full content of each one —context,
alternatives, consequences, review criteria and evidence— lives in
[docs/adr/](adr/README.md), one file per decision.

No ADR has been accepted yet. A proposed option **does not certify
installation or tests**, and the figures it contains are design budgets
until the evidence issue replaces them with real measurements on the Pi 5.

| ADR | Proposed decision | Status | Owner | Missing evidence |
|---|---|---|---|---|
| 001 — Edge AI | Local BirdNET to recognise birds without sending audio | Not yet written | David | Licence, ARM64 installation, inference p95 and memory measured on the Pi 5 ([#8](https://github.com/elenaatorralbo/txori-kantua/issues/8)) |
| [002 — Events](adr/0002-event-transport.md) | MQTT with versioned JSON and QoS 1; deduplicate in the consumer | Proposed | Javier | Independent consumers, validation and duplicate and disconnection tests ([#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#13](https://github.com/elenaatorralbo/txori-kantua/issues/13)) |
| [003 — Persistence](adr/0003-persistence.md) | **SQLite as the single source of truth**; InfluxDB is not deployed | Proposed | Javier | Triple resend, range query, restart and restore; real size and latencies ([#19](https://github.com/elenaatorralbo/txori-kantua/issues/19)) |
| [004 — Visualisation](adr/0004-visualization.md) | Grafana reads SQLite read-only; the REST API is the planned alternative | Proposed | Javier, reviewed by Erik | Plugin installed on ARM64, importable dashboard and API–dashboard equivalence ([#20](https://github.com/elenaatorralbo/txori-kantua/issues/20), [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21)) |
| 005 — Deployment | systemd for the processes that access hardware | Not yet written | Javier | USB and Grove access, and recovery after two reboots ([#29](https://github.com/elenaatorralbo/txori-kantua/issues/29)) |
| 006 — Privacy | Only transient audio in RAM; persist minimal metadata | Not yet written | David | Inspection of temporary files, swap, dumps, logs and traffic ([#11](https://github.com/elenaatorralbo/txori-kantua/issues/11)) |
| [007 — Retention](adr/0007-retention.md) | 30 days of environment and health, 90 of detections, aggregates for the course; resource budget per service | Proposed | Javier | Purge, backup and restore verified; sustained resource measurement ([#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), [#24](https://github.com/elenaatorralbo/txori-kantua/issues/24)) |

ADRs marked "not yet written" have no file: their owner creates them in the
indicated issue, with their own measurements. Empty templates are not added
to give the appearance of coverage.

When an ADR is accepted, date, participants, versions, consequences,
discarded alternatives and links to tests are added. An incompatible change
**is not edited on top**: it requires a new ADR that supersedes the previous
one and, if it affects a published contract, a new version of that contract.
The full procedure is in [docs/adr/README.md](adr/README.md).

Related documents: [MVP scope](mvp-scope.md) and
[interface registry](interfaces.md), which respectively define what enters
the MVP and who owns each contract.
