-- Detection observations, not individual birds. UTC seconds for Grafana.
SELECT observed_at_ms / 1000 AS time, scientific_name, confidence
FROM detections
WHERE observed_at_ms BETWEEN $__from AND $__to
ORDER BY observed_at_ms;

-- Keep failed readings as NULL; never turn missing data into zero.
SELECT observed_at_ms / 1000 AS time, metric, unit, value
FROM environment_readings
WHERE observed_at_ms BETWEEN $__from AND $__to AND quality = 'ok'
ORDER BY observed_at_ms;

-- Health freshness must be read alongside metrics.
SELECT observed_at_ms / 1000 AS time,
       json_extract(payload, '$.cpu_percent') AS cpu_percent,
       json_extract(payload, '$.cpu_temperature_c') AS temperature_c
FROM health_events
WHERE observed_at_ms BETWEEN $__from AND $__to
ORDER BY observed_at_ms;
