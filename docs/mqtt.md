# Initial MQTT contract (proposed)

Design version `v1`, pending team approval. **The executable source of truth is in [contracts/](../contracts/README.md)**: JSON Schema, valid and invalid examples and tests (`pytest tests/contracts`). If this document and the schemas disagree, the schemas win. All examples are synthetic. They are not samples from a working system.

| Topic | Producer → consumer | Proposed QoS / retain |
|---|---|---|
| `txori/v1/{station_id}/detections` | Inference/publisher → ingest and LCD | 1 / false |
| `txori/v1/{station_id}/environment` | Sensors → ingest | 1 / false |
| `txori/v1/{station_id}/health` | Monitor → ingest/dashboard | 1 / true, with timestamp and expiry |
| `txori/v1/{station_id}/availability/{service}` | Service/Last Will → monitor | 1 / true |

`station_id` is a stable logical identifier, without coordinates. ACLs limit producers to their topics. The LCD consumes detections and keeps the latest valid one in RAM; there is no need to retain every event. If a "latest detection" state topic is added, it will carry age and separate semantics, agreed before it is used.

## Detection

```json
{
  "schema_version": "1.0",
  "event_id": "a0a74d86-74b8-4a0c-a2b7-0b0d880766a4",
  "station_id": "station-01",
  "observed_at": "2026-11-17T09:00:00Z",
  "window_end": "2026-11-17T09:00:03Z",
  "species": {"scientific_name": "Turdus merula"},
  "confidence": 0.87,
  "model": {"name": "BirdNET", "version": "example-not-validated"}
}
```

The 3-second window is only illustrative: it will be confirmed according to the model. Score between 0 and 1, not a guaranteed probability nor a definitive identification. Taxonomic key/catalogue to be agreed. ES/EU/EN display names kept separate from the scientific identifier.

## Environment

```json
{
  "schema_version": "1.0",
  "event_id": "d5f170c9-d35e-470c-83b6-932e6e3a60a3",
  "station_id": "station-01",
  "observed_at": "2026-11-17T09:00:00Z",
  "readings": {
    "temperature": {"value": 17.4, "unit": "degC", "quality": "ok"},
    "humidity": {"value": 68.0, "unit": "percent", "quality": "ok"},
    "pressure": {"value": 1012.4, "unit": "hPa", "quality": "ok"},
    "light": {"value": null, "unit": "raw", "quality": "unavailable"}
  }
}
```

Lux only if the model and the conversion have been validated; otherwise unit `raw` with the documented sensor range. A missing reading is `null` with quality `unavailable`/`error`, never an invented zero. Initial proposal: an environmental reading every 30 seconds, to be validated per sensor and resources.

## Health and availability

```json
{
  "schema_version": "1.0",
  "event_id": "72dbceac-c8c8-412b-81f7-15807ce149a3",
  "station_id": "station-01",
  "observed_at": "2026-11-17T09:00:00Z",
  "cpu_percent": 24.0,
  "memory_used_bytes": 600000000,
  "cpu_temperature_c": 51.0,
  "disk_free_bytes": 10000000000,
  "uptime_seconds": 3600,
  "services": {"capture": "healthy", "inference": "healthy"}
}
```

Availability: `{"schema_version":"1.0","station_id":"station-01","service":"capture","status":"online","observed_at":"2026-11-17T09:00:00Z"}`. The Last Will uses `offline`; its timestamp may be the connection time, not the exact time of the failure. The consumer adds `received_at` and uses a heartbeat for expiry.

## Validation, ordering and recovery

- UTC RFC 3339; ingest adds `received_at`. It does not replace the observation time when resending.
- UUID per observation, same ID on every retry. Deduplicate in persistence and avoid repeated LCD effects.
- Validate version, size (proposed maximum 16 KiB), type, unit, range and timestamps; reject incompatible versions without stopping the consumer.
- Do not assume global ordering between topics. An old event does not replace a more recent detection on the LCD.
- QoS 1, bounded queues and backoff with jitter; define acceptable loss and metrics. No audio in a persistent queue.
- Events without retain; retained state always subject to expiry. Initial LCD proposal: recent detection ≤5 minutes, configurable and reviewed with user experience.
- Forbidden: audio samples/base64, transcriptions, credentials, personal paths and precise coordinates.

The schemas, positive and negative examples and tests already exist in [contracts/](../contracts/README.md) ([#10](https://github.com/elenaatorralbo/txori-kantua/issues/10)); team review is still needed before integrating producers and consumers. Clarifications that the executable contract adds to this document: the `observed_at` of a detection is the start of the analysed window; `received_at` never travels in an MQTT message; `availability` carries no `event_id`; and the message `station_id` must match the one in the topic.
