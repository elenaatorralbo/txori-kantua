# Initial REST API

Read-only design, **not implemented**. Planned base `/api/v1`; Flask and the OpenAPI document will be implemented and verified during Sprint 2. The specification is in [`contracts/openapi.yaml`](../contracts/openapi.yaml) ([#10](https://github.com/elenaatorralbo/txori-kantua/issues/10)), with consistency tests in `tests/contracts`; if this document and the OpenAPI disagree, the OpenAPI wins. The endpoints remain **unimplemented** until [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20). Clarifications in the OpenAPI: an out-of-range `limit` is a 400 and is not silently clamped; detections also accept `min_confidence`; and daily aggregates are requested with `from_date`/`to_date` (local days, maximum 92).

| Method and route | Use | Proposed response |
|---|---|---|
| `GET /api/v1/health` | Liveness/readiness without secrets | 200 healthy; 503 required dependency unavailable |
| `GET /api/v1/detections` | Detections by interval, station and species | 200, paginated list |
| `GET /api/v1/environment` | Readings by interval and station | 200, paginated list with units/quality |
| `GET /api/v1/summaries/daily` | Daily aggregates | 200, counts and coverage; final implementation in Sprint 3 |

List parameters: `from`, `to` (UTC RFC 3339, interval `[from,to)`), `station_id`, `limit` (default 100, maximum 500), opaque `cursor`; detections also accept a scientific `species`. Proposal: maximum 31 days per raw-data query, adjustable after measuring. Stable ordering by `(observed_at,event_id)`; a cursor does not change filters. For aggregates, Europe/Madrid local day with explicit UTC start/end, including clock changes.

Synthetic response example:

```json
{
  "items": [{
    "event_id": "a0a74d86-74b8-4a0c-a2b7-0b0d880766a4",
    "station_id": "station-01",
    "observed_at": "2026-11-17T09:00:00Z",
    "received_at": "2026-11-17T09:00:01Z",
    "species": {"scientific_name": "Turdus merula"},
    "confidence": 0.87
  }],
  "next_cursor": null
}
```

Empty query: 200 with `items: []`. Invalid parameters: 400, without silently converting incorrect dates. Non-existent route: 404. Storage unavailable: 503, without returning an empty list that looks like an absence of birds.

```json
{"error":{"code":"INVALID_RANGE","message":"from must precede to","request_id":"example-request-01"}}
```

There is no audio endpoint, sensor write or remote execution. Initial deployment on the local network with restricted access; authentication/TLS and limits will be decided before any external exposure. Do not include secrets in OpenAPI, logs or examples. A public health endpoint, if enabled, only exposes minimal status.

OpenAPI must document all parameters, schemas, errors, pagination, units and security requirements. Contract tests will cover empty data, limits, invalid intervals, visible deduplication, unavailability and equivalence with the dashboard queries. It is not assumed that Grafana uses this API as a direct source.
