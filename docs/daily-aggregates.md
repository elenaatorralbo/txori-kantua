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
| `detections_total: 0` with `coverage.minutes_with_data > 0` | Station running, no birds |
| `coverage.minutes_with_data / minutes_in_day` | Partial days (station off for hours) are visible, not read as quiet days |

## For the dashboard (#21)

- Show a day absent from the result as a gap ("no data"), not as a 0 bar.
- Show coverage next to daily counts; flag days below a coverage threshold
  agreed with the team (proposal: 80 %).
- Group by `date(observed_at, '+1 hour')` is **wrong** for half of the year:
  use the local day bounds, or let the API compute them.

## Limitation

Coverage counts minutes with any event of the station (detection,
environment, health). It shows that the station was alive, not that capture
and inference were running. When those services publish availability (#13),
coverage can be restricted to minutes in which both were `healthy`.
