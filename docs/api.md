# API REST inicial

Diseño de lectura, **no implementado**. Base prevista `/api/v1`; Flask y documento OpenAPI se implementarán y verificarán durante Sprint 2. La especificación inicial aquí debe convertirse a `contracts/openapi.yaml` junto con schemas y pruebas, sin publicar endpoints inexistentes como disponibles.

| Método y ruta | Uso | Respuesta propuesta |
|---|---|---|
| `GET /api/v1/health` | Liveness/readiness sin secretos | 200 saludable; 503 dependencia necesaria no disponible |
| `GET /api/v1/detections` | Detecciones por intervalo, estación y especie | 200, lista paginada |
| `GET /api/v1/environment` | Lecturas por intervalo y estación | 200, lista paginada con unidades/calidad |
| `GET /api/v1/summaries/daily` | Agregados diarios | 200, conteos y cobertura; implementación final Sprint 3 |

Parámetros de listas: `from`, `to` (UTC RFC 3339, intervalo `[from,to)`), `station_id`, `limit` (predeterminado 100, máximo 500), `cursor` opaco; detecciones admite `species` científico. Propuesta: máximo 31 días por consulta de datos crudos, ajustable tras medir. Orden estable por `(observed_at,event_id)`; cursor no cambia filtros. Para agregados, día local Europe/Madrid con inicio/fin UTC explícitos, incluidos cambios horarios.

Ejemplo sintético de respuesta:

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

Consulta vacía: 200 con `items: []`. Parámetros inválidos: 400, sin convertir silenciosamente fechas incorrectas. Ruta inexistente: 404. Almacenamiento no disponible: 503, sin devolver una lista vacía que parezca ausencia de aves.

```json
{"error":{"code":"INVALID_RANGE","message":"from must precede to","request_id":"example-request-01"}}
```

No hay endpoint de audio, escritura de sensores ni ejecución remota. Despliegue inicial en red local con acceso restringido; autenticación/TLS y límites se decidirán antes de cualquier exposición externa. No incluir secretos en OpenAPI, logs ni ejemplos. Health público, si se habilita, solo expone estado mínimo.

OpenAPI deberá documentar todos los parámetros, schemas, errores, paginación, unidades y requisitos de seguridad. Las pruebas de contrato cubrirán datos vacíos, límites, intervalos inválidos, deduplicación visible, indisponibilidad y equivalencia con las consultas del dashboard. No se presupone que Grafana use esta API como fuente directa.
