# Interface registry

Status: proposal by Javier ([#9](https://github.com/elenaatorralbo/txori-kantua/issues/9)),
pending team review. Date: 10/11/2026.

Each system interface has here **a producer, one or more consumers, a contract
owner and a findable contract**. The owner is whoever decides the shape of the
interface and has to approve a change; not necessarily whoever implements it.

Practical rule: if two people need to agree in order to move forward, it
appears in this table. If it does not appear, it is not an interface: it is an
internal detail of a module and its author can change it without notice.

## Messaging interfaces (MQTT)

| Interface | Producer | Consumers | Contract owner | Contract | Issues |
|---|---|---|---|---|---|
| `txori/v1/{station_id}/detections` | Detection publisher (Javier) from inference (David) | Ingest (Javier), LCD station (Elena) | Javier | `contracts/mqtt/detection.schema.json` | [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) → [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), [#22](https://github.com/elenaatorralbo/txori-kantua/issues/22) |
| `txori/v1/{station_id}/environment` | Environmental publisher (Elena) | Ingest (Javier) | Javier | `contracts/mqtt/environment.schema.json` | [#14](https://github.com/elenaatorralbo/txori-kantua/issues/14) → [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19) |
| `txori/v1/{station_id}/health` | Resource monitor (Erik) | Ingest (Javier), dashboard (Erik) | Javier | `contracts/mqtt/health.schema.json` | [#24](https://github.com/elenaatorralbo/txori-kantua/issues/24) → [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21) |
| `txori/v1/{station_id}/availability/{service}` | Every service, including its Last Will | Monitor (Erik), ingest (Javier), LCD (Elena) | Javier | `contracts/mqtt/availability.schema.json` | [#13](https://github.com/elenaatorralbo/txori-kantua/issues/13), [#24](https://github.com/elenaatorralbo/txori-kantua/issues/24) |

## Code interfaces (Python)

These are the seams between modules of different people. Their shape is set in
[#10](https://github.com/elenaatorralbo/txori-kantua/issues/10) and implemented
in the `txori_kantua` package.

| Interface | Offered by | Used by | Owner | Issues |
|---|---|---|---|---|
| `messaging.publisher`: publish a validated event, with retry and stable `event_id` | Javier | David (detections), Elena (environment), Erik (health) | Javier | [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) |
| `messaging.contracts`: build and validate events against the JSON Schemas | Javier | Everyone | Javier | [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10) |
| Inference output: species, confidence, window and model version | David | Detection publisher (Javier) | David, shape agreed with Javier | [#16](https://github.com/elenaatorralbo/txori-kantua/issues/16), [#17](https://github.com/elenaatorralbo/txori-kantua/issues/17) → [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) |
| Sensor adapters: reading with value, unit and quality | Elena | Environmental publisher (Elena) | Elena | [#4](https://github.com/elenaatorralbo/txori-kantua/issues/4), [#14](https://github.com/elenaatorralbo/txori-kantua/issues/14) |
| ES/EU/EN name catalogue by scientific name | Elena | LCD (Elena), API (Javier) | Elena, format agreed with Javier | [#22](https://github.com/elenaatorralbo/txori-kantua/issues/22) |

## Data and service interfaces

| Interface | Producer | Consumers | Owner | Contract | Issues |
|---|---|---|---|---|---|
| SQLite file, **read-only** for everyone except ingest | Ingest (Javier) | API (Javier), Grafana (Erik) | Javier | [ADR 0003](adr/0003-persistence.md) and `storage/schema.sql` | [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19) → [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20), [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21) |
| REST API `/api/v1` | Flask API (Javier) | Clients, Grafana as the alternative (Erik) | Javier | `contracts/openapi.yaml` | [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20) |
| Dashboards exported in `dashboards/` | Erik | Team, demonstration | Erik | Exported JSON and versioned SQL | [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21), [#28](https://github.com/elenaatorralbo/txori-kantua/issues/28) |
| systemd units and operating procedure | Javier | Team | Javier | `deploy/` | [#29](https://github.com/elenaatorralbo/txori-kantua/issues/29) |

## What Javier needs from the others

For Javier's modules (messaging, persistence, API, deployment) to be closed,
somebody else's decision is needed on these points. Until they arrive, work
progresses against fixtures that meet the contract.

| Needed from | What | For | Blocks |
|---|---|---|---|
| David | Concrete shape of the inference output: scientific name, taxonomic key, confidence, window start and end, model name and version | Fixing `detection.schema.json` without assuming | [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) |
| David | Whether BirdNET returns several candidate species per window and whether all of them or only the best one are published | Deciding whether a window produces one or several `event_id` | [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) |
| Elena | Final list of environmental metrics, with the real unit of each sensor | Closing the `metric` and `unit` enumeration | [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10) |
| Elena | Whether light is published in lux or in raw sensor units | Avoiding persisting a unit that later changes | [#14](https://github.com/elenaatorralbo/txori-kantua/issues/14) |
| Elena | How long the LCD considers a detection to be "recent" | Fixing the shared expiry semantics | [#22](https://github.com/elenaatorralbo/txori-kantua/issues/22), [#26](https://github.com/elenaatorralbo/txori-kantua/issues/26) |
| Erik | List of queries the dashboards need | Designing the API so it can replace the SQLite data source | [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20), [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21) |
| Erik | Health fields he wants to monitor | Closing `health.schema.json` | [#24](https://github.com/elenaatorralbo/txori-kantua/issues/24) |
| Team | Approval of [ADR 0003](adr/0003-persistence.md) | Implementing persistence without rewriting it | [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19) |

While one of these answers has not arrived, the corresponding contract uses a
**provisional value marked as such** in the schema itself, so that changing it
is a local edit and not a rewrite.

## What Javier delivers to the others

| For | What they get | When | Issue |
|---|---|---|---|
| Everyone | JSON Schemas, valid and invalid examples and contract tests runnable without hardware | Sprint 1 | [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10) |
| Everyone | Publishing library with validation, retry and stable `event_id` | Sprint 1–2 | [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) |
| Everyone | Reproducible environment and pinned dependencies | Sprint 1 | [#2](https://github.com/elenaatorralbo/txori-kantua/issues/2) |
| Everyone | Broker with per-service ACL and credentials outside Git | Sprint 2 | [#13](https://github.com/elenaatorralbo/txori-kantua/issues/13) |
| Erik | Database with a stable schema and indexes, plus read API | Sprint 2 | [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20) |
| Elena | Detection events with explicit expiry for the LCD | Sprint 2 | [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) |
| Team | systemd services, recovery after reboot and operations manual | Sprint 3 | [#29](https://github.com/elenaatorralbo/txori-kantua/issues/29) |

## How an interface is changed

1. Whoever needs the change opens an issue or comments on the existing one,
   with the reason and the affected consumers.
2. The contract owner decides. If the change is **compatible** (adding an
   optional field), the minor `schema_version` is increased and the examples
   are updated.
3. If the change is **incompatible** (removing or renaming a field, changing a
   unit, changing the meaning of a value), a new version of the topic or REST
   resource is created and the migration plan is agreed with **every**
   consumer before merging. A published contract is not edited in place.
4. The contract tests of
   [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10) are updated
   in the same PR as the contract. A contract without a negative example is
   not finished.
