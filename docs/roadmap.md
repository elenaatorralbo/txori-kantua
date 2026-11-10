# Official roadmap and scope

## Sprint 1 — Foundations · 3–17 November

12 deliverables: inventory and wiring, Pi/Python, Grove Hat, environmental sensors, PIR/touch, LCD, microphone, BirdNET feasibility, architecture/data decisions, contracts, privacy and review/team.

Critical order: inventory → Pi → Hat → sensors/LCD; privacy + microphone → BirdNET evaluation. Architecture and contracts progress in parallel without depending on having every component. Start with inventory, privacy, architectural decisions and provisioning; then Grove and microphone.

Verifiable output on 17/11: reviewed architecture, prioritised Project and backlog, components tested on the Pi with evidence, known risks and implementation plan. If a component is not available, report the non-fulfilment and a recovery plan: absence does not equal a passed test.

## Sprint 2 — Working Pipeline · 17 November–3 December

12 deliverables: broker, environmental publishing, capture, inference, filters, detection publishing, persistence, API, dashboard, LCD station, vertical demonstration and monitoring.

Integration priority: contracts → broker + ingest → real sensor → environmental dashboard. Add birds and LCD on top of that flow without postponing the first demonstration until every module is finished. API and recognition can evolve in parallel on fixtures that meet the contract. The full dashboard later incorporates real bird events.

Mandatory output on 03/12: **Sensor → Processing → Storage → Visualisation**, with a traceable identifier and repeated evidence. Additional committed goal: integrate bird events and the station so that Sprint 3 focuses on quality.

## Sprint 3 — MVP Release · 3–11 December

8 deliverables: recognition quality, resilience, regression/CI, daily aggregates, systemd/reboot, reproducible installation, acceptance/demo and conditional release.

It is a short sprint. Proposal: feature freeze on 08/12, acceptance on 10/12 and margin for fixes/delivery on 11/12. These intermediate dates are a team policy to be confirmed; holidays and real availability must be deducted in planning. Each module's tests are written from its implementation: the CI issue in Sprint 3 consolidates regression, it does not delay all quality work.

Do not create `v1.0.0` because a date arrives: it depends on acceptance, tests, review and documentation. If the MVP fails, communicate status and limitations; do not label it as complete.

## Outside the MVP

Two optional investigations group six improvements: Euskalmet and a Leaflet map; anomalies, Telegram, dawn chorus and period comparisons. No milestone or iteration from the three sprints. They are only considered after accepting the MVP and without delaying delivery.

## Dependencies and load

The [backlog](backlog.md) table contains real dependencies and estimates. Complete deliverables are planned, not one issue per coding instruction. Functional split: David audio/AI, Javier communication/data, Elena hardware/interaction and Erik dashboards/monitoring; integration and reviews are shared. The group and Javier's identity are confirmed by Elena and by the GitHub profile/invitation, respectively. Javier already has his ten issues assigned; confirm capacity and reassign explicitly if necessary before committing to Sprint 2.
