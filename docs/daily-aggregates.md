# Daily aggregates (issue #28)

`txori_kantua.aggregates.daily_summaries` turns stored contract events into
the `DailySummary` items of `GET /api/v1/summaries/daily`
([OpenAPI](../contracts/openapi.yaml)). It is a pure function: the API of
[#20](https://github.com/elenaatorralbo/txori-kantua/issues/20) can call it,
and the dashboards of [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21)
must reproduce the same rules in SQL (ADR 0004). The `daily_summaries` table
of ADR 0003 is a projection that can be rebuilt from the base tables.

## Rules

| Rule | Why |
|---|---|
| A day is the **Europe/Madrid local day**; storage stays UTC; `start_utc`/`end_utc` are explicit | Clock-change days last 23 h (last Sunday of March) and 25 h (last Sunday of October) |
| Bucketing uses the UTC instant converted to local time, never the local clock text | The repeated 02:00–03:00 hour of October holds two different observations |
| Duplicates (same `event_id`) count once | QoS 1 can redeliver; ingest also deduplicates (#19) |
| Environmental statistics only over quality `ok` | A failed reading is a gap, not a 0 (environment contract) |
| A day with no station event is **not returned** | Missing day = no data |
| `detections_total: 0` with `coverage.minutes_with_data > 0` | No detections recorded; listening duration is unknown |
| `coverage.minutes_with_data / minutes_in_day` | Telemetry coverage only; not a denominator for bird rates |

## For the dashboard (#21)

- Show a day absent from the result as a gap ("no data"), not as a 0 bar.
- Show telemetry coverage next to counts and audio coverage as unknown.
  Never use telemetry minutes as the denominator of bird rates.
- Group by `date(observed_at, '+1 hour')` is **wrong** for half of the year:
  use the local day bounds, or let the API compute them.

## Limitation

Coverage counts minutes with any event of the station (detection,
environment, health). It shows that the station was alive, not that capture
and inference were running. `analyzed_audio_minutes` is null until completed
analyzed windows are measured, including windows without detections and gaps.
Availability/healthy status alone does not prove completed analysis.
Environmental coverage must use valid samples of the specific metric, not any
event. Mixed units within a day are rejected instead of silently averaged.
