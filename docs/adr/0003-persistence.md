# 0003 — Use SQLite as the single source of truth of the MVP

- **Status:** Proposed
- **Proposed on:** 10/11/2026
- **Owner:** Javier Santamaría — [javiers2004](https://github.com/javiers2004)
- **Issue:** [#9](https://github.com/elenaatorralbo/txori-kantua/issues/9)
- **Accepted on:** —
- **Affects:** [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19),
  [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20),
  [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21) (Erik),
  [#28](https://github.com/elenaatorralbo/txori-kantua/issues/28) (Erik)

## Context

[architecture.md](../architecture.md) left persistence open between three
options: SQLite for detections plus InfluxDB for series, SQLite only, or
InfluxDB only. It has to be closed before implementing ingest, because the
schema, the API and Erik's dashboards depend on it.

Three constraints shape the choice:

1. **Idempotency.** [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19)
   requires that resending the same event three times produces a single
   observation. With QoS 1 ([ADR 0002](0002-event-transport.md)) duplicates are
   normal.
2. **Resources.** The Raspberry Pi 5 also runs audio capture and BirdNET
   inference. Pi overload is an already identified risk.
3. **Schedule.** Three short sprints remain. Every additional service costs
   installation time, credentials, ARM64 validation and operation.

## Decision

**SQLite is the single source of truth of every persisted observation**
(detections, environment, health and availability transitions). InfluxDB is not
deployed in the MVP.

- A single database file, in **WAL** mode, with `event_id` as the primary key
  and `INSERT ... ON CONFLICT DO NOTHING` writes. Deduplication is a property of
  the schema, not code that can be forgotten.
- **A single process writes**: the ingest service. The API, Grafana and any
  analysis tool open the database **read-only**. WAL allows concurrent readers
  while there is a writer.
- Timestamps are stored as an **integer of UTC epoch milliseconds**
  (`observed_at_ms`, `received_at_ms`). RFC 3339 is the contract format; the
  conversion happens at the edges. Precision finer than a millisecond is
  truncated, and this is written into the contract of
  [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10).
- Daily aggregates ([#28](https://github.com/elenaatorralbo/txori-kantua/issues/28))
  are a **rebuildable projection** of the base tables, never data that only
  exists aggregated.

### Source of truth per datum

| Datum | Authoritative source | Derived | Rebuildable? |
|---|---|---|---|
| Bird detections | SQLite, `detections` table | daily aggregates, dashboards, API | Yes |
| Environmental readings | SQLite, `environment_events` + `environment_readings` | aggregates, dashboards, API | Yes |
| Pi health | SQLite, `health_events` | dashboards | Yes |
| **Current** availability of a service | Retained MQTT topic | status dashboard | No: by definition it is live state |
| Availability history | SQLite, `availability_transitions` | dashboards | Yes |
| ES/EU/EN common names | Catalogue file versioned in Git | LCD, API | Yes |
| Station configuration and credentials | Local files outside Git | — | No; backed up through the procedure of [#29](https://github.com/elenaatorralbo/txori-kantua/issues/29) |

No datum has two writers. There are no dual writes, so no reconciliation
strategy is needed.

## Alternatives considered

| Alternative | For | Against | Why it is not chosen now |
|---|---|---|---|
| **SQLite + InfluxDB** (initial proposal) | Native time series; Grafana ships a first-party data source | Dual writes with two consistency models; two services to operate; reconciliation after a partial failure is real work | It adds the most expensive problem of the project, recovery after partial failure, in exchange for dashboard convenience |
| **InfluxDB only** | A single store; built-in retention; direct Grafana | It deduplicates by measurement, tags and time. Deduplicating by `event_id` would require making it a tag, and a tag with a unique value per event blows up series cardinality: the classic anti-pattern and a real memory cost on a Pi | It breaks the idempotency criterion of [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), or it breaks the memory budget |
| **PostgreSQL or TimescaleDB** | Full relational model, real concurrency | Heavy service, users and backups to manage, with no need for one writer and tens of MB | Disproportionate for the volume computed below |
| **CSV or JSONL files** | Trivial to write | No deduplication, no range queries, no transactions | It meets none of the acceptance criteria of [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19) |

## Estimated volume

Assumptions: one station, environment every 30 s, health every 60 s, 2,000
daily detections as a pessimistic upper bound and the retention of
[ADR 0007](0007-retention.md). Row size estimated **including indexes**.

| Table | Rows/day | Bytes/row | Retention | Steady-state size |
|---|---:|---:|---:|---:|
| `environment_events` | 2,880 | ~150 | 30 d | ~13 MB |
| `environment_readings` (4 metrics) | 11,520 | ~150 | 30 d | ~52 MB |
| `health_events` | 1,440 | ~200 | 30 d | ~9 MB |
| `detections` | ≤2,000 | ~200 | 90 d | ≤36 MB |
| `availability_transitions` | tens | ~120 | 90 d | <1 MB |
| `daily_summaries` | tens | ~150 | course | <1 MB |
| | | | **Total** | **~110 MB; <250 MB with margin** |

These are design figures for sizing, **not measurements**. They are replaced by
the real file size in the evidence of
[#19](https://github.com/elenaatorralbo/txori-kantua/issues/19).

## Consequences

- The deduplication of [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19)
  is achieved with a `PRIMARY KEY` constraint, without application logic prone
  to race conditions.
- The restore test is solved with `VACUUM INTO` on a file: a consistent hot
  copy, without stopping ingest or dumping credentials.
- One less service to install, secure, validate on ARM64 and monitor.
- **Constraint that affects the whole team:** nobody else writes to the
  database. Whoever needs to write publishes to MQTT. A dashboard or a script
  that opens the database for writing can block ingest.
- Grafana has no first-party SQLite data source. This is solved in
  [ADR 0004](0004-visualization.md) and is the main risk of this decision.
- If the project grew to several stations with concurrent writers, this
  decision would not scale and would have to be replaced. That is outside the
  MVP.

## Review criteria

This decision is reopened if any measurable condition is met:

- The p95 latency of writing an event exceeds **50 ms** on the Pi 5 with the
  nominal load, or `SQLITE_BUSY` errors appear that ingest does not absorb
  with its retry.
- The file exceeds **2 GB**, or the projected growth exceeds the budget of
  [ADR 0007](0007-retention.md).
- A dashboard query over the maximum allowed range, 31 days, takes more than
  **2 s** after adding indexes and daily aggregates.
- Neither the SQLite data source nor the API alternative of
  [ADR 0004](0004-visualization.md) is usable on ARM64.

## Evidence

Pending. Produced by:

- [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19): schema,
  triple-resend test, range query, restart and restore.
- [#28](https://github.com/elenaatorralbo/txori-kantua/issues/28): rebuilding
  aggregates and query times.
- Real file size and latencies measured on the Pi 5, not estimated.
