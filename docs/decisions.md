# Initial technical decision record

All ADRs in this table are **proposed**, pending review in Sprint 1. A proposed option does not certify installation or tests.

| ADR | Proposal and reason | Alternatives | Evidence needed to accept |
|---|---|---|---|
| 001 — Edge AI | Local BirdNET for recognition without sending audio | Another compatible runtime/model; less frequent capture | Licence, ARM64 installation, inference p95 and memory measured on the Pi 5 |
| 002 — Events | Mosquitto, versioned JSON and QoS 1 | Direct inter-process communication, HTTP | Independent consumers, validation and duplicate/disconnection tests |
| 003 — Persistence | SQLite for detections/idempotency and InfluxDB for series/projections | SQLite only; InfluxDB only | Operational complexity, idempotency, queries and Grafana data source verified |
| 004 — Visualisation | Grafana as the main dashboard; Flask as an independent API | Own frontend on Flask | Importable dashboard, consistent queries and resource consumption |
| 005 — Deployment | systemd for processes that access hardware | Containers for auxiliary services or the whole stack | USB/Grove access and recovery after two reboots; ARM64 images tested if used |
| 006 — Privacy | Only transient audio in RAM; persist minimal metadata | Storing conversations or sending audio is not accepted | Inspection of temporary files, swap, dumps, logs and traffic |
| 007 — Retention | Proposal: 30 days of environment/health, 90 of detections, aggregates for the duration of the course | Shorter retention depending on capacity | Disk budget and team approval; purge and backup/restore verified |

Each accepted ADR will add date, participants, versions, decision, consequences, discarded alternatives and links to tests. An incompatible change requires a new ADR and a new contract version. The retention figures are an operational proposal, not a legal requirement.
