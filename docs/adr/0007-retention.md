# 0007 — Retention per data type and resource budget

- **Status:** Proposed
- **Proposed on:** 10/11/2026
- **Owner:** Javier Santamaría — [javiers2004](https://github.com/javiers2004)
- **Issue:** [#9](https://github.com/elenaatorralbo/txori-kantua/issues/9)
- **Accepted on:** —

## Context

The project needs an explicit deletion policy for two reasons: the Raspberry
Pi card is finite and data minimisation is a principle of
[privacy.md](../privacy.md). Without a policy, the database grows until it
fills the disk and the failure shows up on demonstration day.

Retention is not a legal requirement here: the persisted data is environmental
and detection metadata, with no personal data. It is an operational team
decision.

## Decision

### Retention per data type

| Data | Retention | Reason |
|---|---|---|
| `environment_readings` and `environment_events` | **30 days** | Dominant volume; long trends are kept aggregated |
| `health_events` | **30 days** | Only the recent past matters for diagnosis |
| `detections` | **90 days** | It is the data with observational value and the lowest volume |
| `availability_transitions` | **90 days** | Negligible volume, useful to justify outages |
| `daily_summaries` | **No purge during the course** | Small aggregate; it supports time comparisons |
| Rejected records (`rejected_events`) | **14 days** | They serve to diagnose a broken producer, not as an archive |

The purge is run **by the ingest service**, once a day, in a bounded
transaction, and logs how many rows it deleted from each table. It is not a
manual task or a separate `cron` that can be forgotten.

Before purging the raw data of a day, the **aggregates of that day must have
been computed**. If they have not, the purge of that day is postponed and a
warning is logged: data whose projection does not exist yet is never lost.

### Resource budget on the Raspberry Pi 5

Design budget that Javier's services commit not to exceed, and that defines how
much is left for audio and inference:

| Service | Target RSS | Target average CPU | Owner |
|---|---:|---:|---|
| Mosquitto | ≤100 MB | ≤5 % | Javier |
| Ingest | ≤150 MB | ≤10 % | Javier |
| Flask API | ≤150 MB | ≤5 % | Javier |
| Grafana | ≤400 MB | ≤10 % | Erik |
| **Infrastructure subtotal** | **≤800 MB** | **≤30 %** | |
| Available for capture, inference, station and OS | the rest | the rest | David, Elena |

| Resource | Budget |
|---|---|
| Database in steady state | ≤250 MB, warning at 70 % and alert at 90 % |
| Minimum free disk space | ≥2 GB; below that, ingest enters degraded mode ([#26](https://github.com/elenaatorralbo/txori-kantua/issues/26)) |
| Backup | Daily, `VACUUM INTO`, 7 rotated copies |

All figures are **unmeasured design targets**. The Pi is not verified yet.
They are replaced by measurements in
[#24](https://github.com/elenaatorralbo/txori-kantua/issues/24) and
[#29](https://github.com/elenaatorralbo/txori-kantua/issues/29).

### Backups

- Metadata only: the database and the configuration without secrets. Never
  audio, never credentials, never `.env`.
- `VACUUM INTO` produces a consistent copy without stopping ingest.
- A backup that has never been restored does not count as a backup: restore is
  tested and linked as evidence in
  [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19).

## Alternatives considered

| Alternative | For | Against | Why it is not chosen now |
|---|---|---|---|
| No purge during the course | Nothing to implement; no data is lost | The volume is affordable, but it leaves the system without defined behaviour on a full disk and contradicts minimisation | The degraded mode of [#26](https://github.com/elenaatorralbo/txori-kantua/issues/26) needs a threshold; without a policy there is no threshold |
| Uniform 30-day retention for everything | Simpler to explain | Loses detections, which are the valuable data and the cheapest to keep | Keeping 90 days of detections costs ~36 MB |
| Reduce environmental sampling instead of purging | Less data from the source | Loses live resolution, which the dashboards do need | Kept as a lever if real measurement contradicts the budget |
| Purge by size instead of by age | Guaranteed disk cap | Unpredictable retention: a noisy day would delete weeks | Age is explainable; size acts as an alarm, not as a criterion |

## Consequences

- Ingest gains a daily responsibility and a mandatory ordering with respect to
  the aggregates of [#28](https://github.com/elenaatorralbo/txori-kantua/issues/28).
- Dashboards over more than 30 days can only be built on aggregates. Erik must
  take it into account when designing
  [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21) and
  [#28](https://github.com/elenaatorralbo/txori-kantua/issues/28).
- The resource budget gives David and Elena a concrete figure of how much the
  infrastructure leaves free, instead of discovering it during integration.

## Review criteria

- Real measurement contradicts the estimated volume by more than a factor of
  **2**.
- Free space drops below 2 GB despite the purge.
- The demonstration needs a longer history than the retention set.
- A service exceeds its memory budget in a sustained way.

## Evidence

Pending. Produced by:

- [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19): purge,
  backup and restore verified, with the real file size.
- [#24](https://github.com/elenaatorralbo/txori-kantua/issues/24) (Erik):
  sustained measurement of CPU, memory, temperature and disk.
- [#29](https://github.com/elenaatorralbo/txori-kantua/issues/29): low disk
  space test and behaviour in degraded mode.
