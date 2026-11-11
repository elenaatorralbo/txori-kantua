# Architecture decision records (ADR)

This directory contains the architecture decisions as individual, versioned
files. It replaces the summary table in [decisions.md](../decisions.md), which
is kept as a one-line-per-ADR index.

## Statuses

| Status | Meaning |
|---|---|
| `Proposed` | Written by its owner. Not yet reviewed by the team. |
| `Accepted` | Reviewed and approved in planning or refinement, with date and participants. |
| `Rejected` | Discarded. The document is kept with the reason. |
| `Superseded by NNNN` | Replaced by another ADR. The original is never deleted or rewritten. |

A `Proposed` ADR **does not certify installation, measurement or testing**. The
figures it contains are design budgets until the evidence issue replaces them
with real measurements on the Raspberry Pi 5.

## Index

| ADR | Title | Status | Owner | Evidence issue |
|---|---|---|---|---|
| 0001 | Local inference with BirdNET | Not yet written | David | [#8](https://github.com/elenaatorralbo/txori-kantua/issues/8) |
| [0002](0002-event-transport.md) | Event transport over MQTT and versioned JSON | Proposed | Javier | [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#13](https://github.com/elenaatorralbo/txori-kantua/issues/13) |
| [0003](0003-persistence.md) | SQLite as the single source of truth | Proposed | Javier | [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19) |
| [0004](0004-visualization.md) | Grafana data source and role of the API | Proposed | Javier, reviewed by Erik | [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20), [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21) |
| 0005 | systemd as the deployment mechanism | Not yet written | Javier | [#29](https://github.com/elenaatorralbo/txori-kantua/issues/29) |
| 0006 | Transient audio in RAM | Not yet written | David | [#11](https://github.com/elenaatorralbo/txori-kantua/issues/11) |
| [0007](0007-retention.md) | Retention and resource budget | Proposed | Javier | [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), [#28](https://github.com/elenaatorralbo/txori-kantua/issues/28) |

ADRs marked "Not yet written" have no file yet: they are created in the
indicated issue, by their owner and with their measurements. Empty templates
are not added to give the appearance of coverage.

## Procedure

1. Copy [`TEMPLATE.md`](TEMPLATE.md) to `NNNN-short-title.md` with the next free
   number. Numbers are never reused.
2. Write it with status `Proposed` and open a PR linking the issue that
   motivates it.
3. Review it in planning or refinement. On acceptance, add date, participants
   and links to the evidence that supports the decision.
4. A change incompatible with an accepted ADR **is not edited on top**: a new
   ADR supersedes it and, if it affects a published contract, the contract
   version is increased as described in [mqtt.md](../mqtt.md) and
   [api.md](../api.md).
5. Update this index and the table in [decisions.md](../decisions.md).
