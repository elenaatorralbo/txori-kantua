# Roadmap oficial y alcance

## Sprint 1 — Foundations · 3–17 noviembre

12 entregables: inventario y cableado, Pi/Python, Grove Hat, sensores ambientales, PIR/touch, LCD, micrófono, viabilidad BirdNET, decisiones de arquitectura/datos, contratos, privacidad y revisión/equipo.

Orden crítico: inventario → Pi → Hat → sensores/LCD; privacidad + micrófono → evaluación BirdNET. Arquitectura y contratos avanzan en paralelo sin depender de disponer de todos los componentes. Empezar por inventario, privacidad, decisiones arquitectónicas y provisión; después Grove y micrófono.

Salida verificable el 17/11: arquitectura revisada, Project y backlog priorizado, componentes probados en Pi con evidencias, riesgos conocidos y plan de implementación. Si un componente no está disponible, informar de incumplimiento y plan de recuperación: la ausencia no equivale a prueba superada.

## Sprint 2 — Working Pipeline · 17 noviembre–3 diciembre

12 entregables: broker, publicación ambiental, captura, inferencia, filtros, publicación de detecciones, persistencia, API, dashboard, estación LCD, demostración vertical y monitorización.

Prioridad de integración: contratos → broker + ingesta → sensor real → panel ambiental. Añadir aves y LCD sobre ese flujo sin posponer la primera demostración hasta acabar todos los módulos. API y reconocimiento pueden evolucionar en paralelo sobre fixtures que cumplan contrato. El dashboard completo incorpora después eventos de aves reales.

Salida obligatoria el 03/12: **Sensor → Procesamiento → Almacenamiento → Visualización**, con identificador trazable y evidencia repetida. Objetivo adicional comprometido: integrar eventos de aves y estación para dejar el Sprint 3 centrado en calidad.

## Sprint 3 — MVP Release · 3–11 diciembre

8 entregables: calidad de reconocimiento, resiliencia, regresión/CI, agregados diarios, systemd/reinicio, instalación reproducible, aceptación/demo y release condicionada.

Es un sprint corto. Proponer congelación funcional el 08/12, aceptación el 10/12 y margen para correcciones/entrega el 11/12. Estas fechas intermedias son una política del equipo por confirmar; los festivos y disponibilidad real deben descontarse en planning. Los tests de cada módulo se escriben desde su implementación: la issue de CI en Sprint 3 consolida regresión, no retrasa toda la calidad.

No crear `v1.0.0` por llegar una fecha: depende de aceptación, pruebas, revisión y documentación. Si falla el MVP, comunicar estado y limitaciones; no etiquetarlo como completado.

## Fuera del MVP

Dos investigaciones opcionales agrupan seis mejoras: Euskalmet y mapa Leaflet; anomalías, Telegram, coro del amanecer y comparativas entre periodos. Sin milestone ni iteración de los tres sprints. Solo se consideran tras aceptar MVP y sin retrasar entrega.

## Dependencias y carga

La tabla de [backlog](backlog.md) contiene dependencias reales y estimaciones. Se planifican entregables completos, no una issue por cada instrucción de código. Reparto funcional: David audio/AI, Javier comunicación/datos, Elena hardware/interacción y Erik paneles/monitorización; integración y revisiones son compartidas. Si Javier o el tamaño de equipo no se confirman, reasignar explícitamente antes de comprometer el Sprint 2. No usar cuentas deducidas de nombres.
