# Evidencia de aceptación

Ninguna comprobación está superada por crear este documento. Enlazar resultados en las issues correspondientes y revisar con otro miembro.

| Puerta | Evidencia mínima | Bloquea |
|---|---|---|
| Fundamentos | Inventario real, Pi/Grove, sensores, LCD, USB; versiones y pruebas fechadas | Cierre de Sprint 1 |
| Viabilidad AI | Corpus autorizado, p50/p95, RAM/CPU/temperatura y decisión | Compromiso de pipeline AI |
| Pipeline | Tres cambios físicos trazados por ID desde sensor hasta panel, con persistencia | Revisión 03/12 |
| Contratos | Ejemplos válidos e inválidos, unidades, versiones y duplicados | Integración |
| Interacción | PIR/touch, ES/EU/EN, eventos caducados y apagado 20 ±1 s | Aceptación MVP |
| Fiabilidad | Corte de broker 60 s, BD caída, sensor ausente y dos reinicios completos | Aceptación MVP |
| Privacidad | Auditoría de disco/memoria persistente, payloads y tráfico sin audio | Toda captura y release |
| Entrega | Ensayo 60 min, CI, instalación por otro miembro y PR revisadas | `v1.0.0` |

Las pruebas de lógica usan pytest y dobles de hardware; las físicas son manuales reproducibles. Se conservarán solo tablas, logs sanitizados, métricas y fotografías/vídeo que no revelen personas ni información sensible. Toda evidencia indica fecha, commit, equipo, versiones, condiciones, resultado y límites.

Propuesta de guion (5–7 minutos): propósito/privacidad, cambio ambiental hasta dashboard, detección de ave con corpus autorizado claramente identificado si no hay aves presentes, interacción LCD, fallo/recuperación y límites. La contingencia no sustituye pruebas físicas ya exigidas. Cada integrante debe explicar una interfaz que no haya implementado personalmente.
