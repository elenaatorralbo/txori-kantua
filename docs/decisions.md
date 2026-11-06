# Registro inicial de decisiones técnicas

Todos los ADR de esta tabla están **propuestos**, pendientes de revisión en Sprint 1. Una opción propuesta no acredita instalación ni pruebas.

| ADR | Propuesta y motivo | Alternativas | Evidencia necesaria para aceptar |
|---|---|---|---|
| 001 — Edge AI | BirdNET local para reconocimiento sin enviar audio | Otro runtime/modelo compatible; captura menos frecuente | Licencia, instalación ARM64, p95 de inferencia y memoria medidas en Pi 5 |
| 002 — Eventos | Mosquitto, JSON versionado y QoS 1 | Comunicación directa entre procesos, HTTP | Consumidores independientes, validación y prueba de duplicados/desconexión |
| 003 — Persistencia | SQLite para detecciones/idempotencia e InfluxDB para series/proyecciones | Solo SQLite; solo InfluxDB | Complejidad de operación, idempotencia, consultas y fuente de datos Grafana verificadas |
| 004 — Visualización | Grafana como dashboard principal; Flask como API independiente | Frontend propio sobre Flask | Dashboard importable, consultas coherentes y consumo de recursos |
| 005 — Despliegue | systemd para procesos que acceden al hardware | Contenedores para servicios auxiliares o toda la pila | Acceso a USB/Grove y recuperación tras dos reinicios; imágenes ARM64 probadas si se usan |
| 006 — Privacidad | Solo audio transitorio en RAM; persistir metadatos mínimos | No se acepta almacenamiento de conversaciones ni envío de audio | Inspección de temporales, swap, volcados, logs y tráfico |
| 007 — Retención | Propuesta: 30 días de ambiente/salud, 90 de detecciones, agregados durante el curso | Retención menor según capacidad | Presupuesto de disco y aprobación del equipo; purga y copia/restauración verificadas |

Cada ADR aceptado añadirá fecha, participantes, versiones, decisión, consecuencias, alternativas descartadas y enlaces a pruebas. Un cambio incompatible requiere nuevo ADR y versión de contrato. Las cifras de retención son una propuesta operativa, no un requisito legal.
