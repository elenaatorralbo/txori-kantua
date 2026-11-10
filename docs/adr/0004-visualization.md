# 0004 — Grafana reads SQLite directly; the API is the client interface

- **Status:** Proposed
- **Proposed on:** 10/11/2026
- **Owner:** Javier Santamaría — [javiers2004](https://github.com/javiers2004)
- **Review needed from:** Erik Eguskiza — [eeguskiza](https://github.com/eeguskiza)
- **Issue:** [#9](https://github.com/elenaatorralbo/txori-kantua/issues/9)
- **Accepted on:** —

## Context

[ADR 0003](0003-persistence.md) sets SQLite as the source of truth. SQLite has
no first-party data source in Grafana, so it has to be decided **how Grafana
reaches the data** before Erik starts
[#21](https://github.com/elenaatorralbo/txori-kantua/issues/21). It is the
main risk introduced by ADR 0003 and must not stay implicit.

The README already warns that it is not assumed that Grafana consumes Flask.
This decision closes the question.

## Decision

**Main path:** Grafana reads the SQLite file **read-only** through the
`frser-sqlite-datasource` data source, installed on the Pi itself.

**Alternative path, already planned:** if that plugin cannot be installed or
does not work on ARM64, Grafana consumes the REST API of
[#20](https://github.com/elenaatorralbo/txori-kantua/issues/20) through the
`yesoreyeram-infinity-datasource` data source.

For the alternative to be really viable and not a plan on paper:

- The API of [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20)
  must cover **the same queries** the dashboards need: time range, station,
  species, pagination and daily aggregates. This is a design requirement of the
  API, not a later add-on.
- Erik and Javier agree on the list of dashboard queries **before**
  implementing the API, so that no dashboard query depends on arbitrary SQL
  the API cannot answer.
- The SQL queries of the dashboards are stored in `dashboards/` together with
  the exported JSON, so that moving to the alternative path means translating
  known queries and not rediscovering them.

**Associated decision:** the Flask API is **not** a web frontend. The MVP
includes no web interface of its own; Grafana is the dashboard. Flask exists
for programmatic clients, for contract verification and as a fallback for
Grafana.

## Alternatives considered

| Alternative | For | Against | Why it is not chosen now |
|---|---|---|---|
| **Grafana on InfluxDB** | First-party, supported data source | Forces reverting [ADR 0003](0003-persistence.md) and brings dual writes back | The cost falls on idempotency and resources, which are acceptance criteria |
| **Grafana only through the API (Infinity)** from the start | A single read path, under our control; no database plugins | Loses SQL aggregation; the API must implement every transformation a dashboard needs | Kept as the alternative, not as the main path, so as not to tie the API to the dashboard schedule |
| **Own web frontend on Flask** | Full control of presentation | Interface work that no MVP criterion requires, with Grafana already chosen | Outside the MVP scope; see [mvp-scope.md](../mvp-scope.md) |
| **Export CSV and plot separately** | No services | There is no live dashboard, which is a criterion of the 03/12 review | It does not meet the Sprint 2 Sprint Goal |

## Consequences

- Grafana opens the database **read-only**. It is mandatory: a second writer
  would break the model of [ADR 0003](0003-persistence.md).
- A dependency on a community plugin appears. Its version must be pinned and
  its installation on ARM64 verified **during Sprint 2**, not at the end,
  because activating the alternative in time depends on it.
- The API gains an explicit requirement: covering the dashboard queries. It
  affects the design of [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20)
  and the aggregates of [#28](https://github.com/elenaatorralbo/txori-kantua/issues/28).
- Dashboards are versioned as exports in `dashboards/`, reproducible from
  scratch; a dashboard edited only in the Grafana interface is not a
  deliverable.

## Review criteria

- The SQLite plugin does not install, does not start or fails on ARM64: the
  alternative path is activated and recorded in this ADR.
- A dashboard query over the maximum range exceeds **2 s** through both paths:
  escalate to precomputed aggregates
  ([#28](https://github.com/elenaatorralbo/txori-kantua/issues/28)) or reopen
  [ADR 0003](0003-persistence.md).
- Grafana on the Pi exceeds the memory budget of
  [ADR 0007](0007-retention.md): consider moving Grafana to another machine on
  the local network, keeping audio and inference on the Pi.

## Evidence

Pending. Produced by:

- [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21) (Erik):
  installation of the data source on ARM64 with the recorded version,
  dashboard importable from `dashboards/` and resource consumption.
- [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20) (Javier):
  equivalence between the API responses and the dashboard queries.
- Written agreement on the list of dashboard queries between Erik and Javier,
  before implementing the API.
