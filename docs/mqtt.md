# Contrato MQTT inicial (propuesto)

Versión de diseño `v1`, pendiente de aprobación y JSON Schema ejecutable en la issue de contratos. Todos los ejemplos son sintéticos. No son muestras de un sistema funcionando.

| Topic | Productor → consumidor | QoS / retain propuestos |
|---|---|---|
| `txori/v1/{station_id}/detections` | Inferencia/publicador → ingesta y LCD | 1 / false |
| `txori/v1/{station_id}/environment` | Sensores → ingesta | 1 / false |
| `txori/v1/{station_id}/health` | Monitor → ingesta/dashboard | 1 / true, con timestamp y caducidad |
| `txori/v1/{station_id}/availability/{service}` | Servicio/Last Will → monitor | 1 / true |

`station_id` es un identificador lógico estable, sin coordenadas. ACL limita productores a sus topics. LCD consume detecciones y conserva en RAM la última válida; no se necesita retener todo evento. Si se añade un topic de estado «última detección», llevará antigüedad y semántica separadas, acordadas antes de su uso.

## Detección

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

Ventana de 3 segundos solo ilustrativa: se confirmará según modelo. Score entre 0 y 1, no probabilidad garantizada ni identificación definitiva. Clave taxonómica/catálogo por acordar. Nombres de presentación ES/EU/EN separados del identificador científico.

## Ambiente

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

Lux únicamente si el modelo y la conversión se han validado; de lo contrario unidad `raw` con rango del sensor documentado. Una lectura ausente es `null` y calidad `unavailable`/`error`, nunca un cero inventado. Propuesta inicial: lectura ambiental cada 30 segundos, a validar por sensor y recursos.

## Salud y disponibilidad

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

Disponibilidad: `{"schema_version":"1.0","station_id":"station-01","service":"capture","status":"online","observed_at":"2026-11-17T09:00:00Z"}`. Last Will usa `offline`; su timestamp puede ser el de conexión, no la hora exacta del fallo. El consumidor añade `received_at` y usa heartbeat para caducidad.

## Validación, orden y recuperación

- UTC RFC 3339; ingesta añade `received_at`. No sustituye tiempo de observación al reenviar.
- UUID por observación, mismo ID en cada reintento. Deduplicar en persistencia y evitar efectos LCD repetidos.
- Validar versión, tamaño (propuesta máxima 16 KiB), tipo, unidad, rango y timestamps; rechazar versiones incompatibles sin detener el consumidor.
- No suponer orden global entre topics. Evento antiguo no reemplaza una detección más reciente en LCD.
- QoS 1, colas acotadas y backoff con jitter; definir pérdida aceptable y métricas. Nada de audio en cola persistente.
- Eventos sin retain; estado retenido siempre sujeto a caducidad. Propuesta inicial LCD: detección reciente ≤5 minutos, configurable y revisada con experiencia de usuario.
- Prohibidos muestras/base64 de audio, transcripciones, credenciales, rutas personales y coordenadas precisas.

La issue de contratos creará schemas, fixtures positivos/negativos y pruebas de compatibilidad antes de integrar productores y consumidores.
