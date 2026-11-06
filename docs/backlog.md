# Product Backlog inicial

34 entregables creados el 05/11/2026. Todos abiertos y en Backlog al configurar el proyecto. Las issues y el Project son la fuente operativa; esta tabla es la línea base inicial, no un informe de progreso en vivo. Estimaciones propuestas, pendientes de planning.

## Sprint 1

| Issue | Área | Prioridad | Responsable propuesto | Puntos | Dependencias |
|---|---|---|---|---|---|
| [#1 Verify hardware inventory and safe wiring](https://github.com/elenaatorralbo/txori-kantua/issues/1) | Hardware | Critical | Elena | 3 | — |
| [#2 Provision Raspberry Pi OS and reproducible Python environment](https://github.com/elenaatorralbo/txori-kantua/issues/2) | DevOps | Critical | Javier | 5 | [#1](https://github.com/elenaatorralbo/txori-kantua/issues/1) |
| [#3 Validate Grove Base Hat compatibility and buses](https://github.com/elenaatorralbo/txori-kantua/issues/3) | Hardware | Critical | Elena | 3 | [#1](https://github.com/elenaatorralbo/txori-kantua/issues/1), [#2](https://github.com/elenaatorralbo/txori-kantua/issues/2) |
| [#4 Validate temperature humidity pressure and light sensors](https://github.com/elenaatorralbo/txori-kantua/issues/4) | Hardware | High | Erik | 5 | [#3](https://github.com/elenaatorralbo/txori-kantua/issues/3) |
| [#5 Validate PIR and touch sensor signals](https://github.com/elenaatorralbo/txori-kantua/issues/5) | Hardware | High | Elena | 3 | [#3](https://github.com/elenaatorralbo/txori-kantua/issues/3) |
| [#6 Validate Grove RGB LCD output and character constraints](https://github.com/elenaatorralbo/txori-kantua/issues/6) | Hardware | High | Elena | 3 | [#3](https://github.com/elenaatorralbo/txori-kantua/issues/3) |
| [#7 Validate USB microphone capture on Raspberry Pi](https://github.com/elenaatorralbo/txori-kantua/issues/7) | Hardware | Critical | David | 3 | [#2](https://github.com/elenaatorralbo/txori-kantua/issues/2), [#11](https://github.com/elenaatorralbo/txori-kantua/issues/11) |
| [#8 Evaluate BirdNET feasibility and resource budget on Pi 5](https://github.com/elenaatorralbo/txori-kantua/issues/8) | AI | High | David | 5 | [#7](https://github.com/elenaatorralbo/txori-kantua/issues/7) |
| [#9 Agree architecture storage decisions and MVP boundaries](https://github.com/elenaatorralbo/txori-kantua/issues/9) | Data | Critical | Javier | 3 | — |
| [#10 Define versioned MQTT and REST contracts](https://github.com/elenaatorralbo/txori-kantua/issues/10) | Backend | Critical | Javier | 5 | [#9](https://github.com/elenaatorralbo/txori-kantua/issues/9) |
| [#11 Define and verify local audio privacy safeguards](https://github.com/elenaatorralbo/txori-kantua/issues/11) | Testing | Critical | David | 3 | — |
| [#12 Prepare Sprint 1 review and confirm team capacity](https://github.com/elenaatorralbo/txori-kantua/issues/12) | Documentation | High | David | 3 | [#9](https://github.com/elenaatorralbo/txori-kantua/issues/9) |

## Sprint 2

| Issue | Área | Prioridad | Responsable propuesto | Puntos | Dependencias |
|---|---|---|---|---|---|
| [#13 Configure Mosquitto with scoped access and health checks](https://github.com/elenaatorralbo/txori-kantua/issues/13) | Backend | Critical | Javier | 3 | [#2](https://github.com/elenaatorralbo/txori-kantua/issues/2), [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10) |
| [#14 Publish validated environmental readings over MQTT](https://github.com/elenaatorralbo/txori-kantua/issues/14) | Backend | Critical | Elena | 5 | [#4](https://github.com/elenaatorralbo/txori-kantua/issues/4), [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#13](https://github.com/elenaatorralbo/txori-kantua/issues/13) |
| [#15 Implement bounded in-memory audio capture windows](https://github.com/elenaatorralbo/txori-kantua/issues/15) | AI | Critical | David | 5 | [#7](https://github.com/elenaatorralbo/txori-kantua/issues/7), [#8](https://github.com/elenaatorralbo/txori-kantua/issues/8), [#11](https://github.com/elenaatorralbo/txori-kantua/issues/11) |
| [#16 Integrate BirdNET inference and normalized detections](https://github.com/elenaatorralbo/txori-kantua/issues/16) | AI | Critical | David | 5 | [#8](https://github.com/elenaatorralbo/txori-kantua/issues/8), [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#15](https://github.com/elenaatorralbo/txori-kantua/issues/15) |
| [#17 Configure seasonal geographic and confidence filtering](https://github.com/elenaatorralbo/txori-kantua/issues/17) | AI | High | David | 3 | [#16](https://github.com/elenaatorralbo/txori-kantua/issues/16) |
| [#18 Publish bird detection events for storage and LCD](https://github.com/elenaatorralbo/txori-kantua/issues/18) | Backend | Critical | Javier | 3 | [#13](https://github.com/elenaatorralbo/txori-kantua/issues/13), [#16](https://github.com/elenaatorralbo/txori-kantua/issues/16), [#17](https://github.com/elenaatorralbo/txori-kantua/issues/17) |
| [#19 Persist MQTT events with idempotent writes and retention](https://github.com/elenaatorralbo/txori-kantua/issues/19) | Data | Critical | Javier | 5 | [#9](https://github.com/elenaatorralbo/txori-kantua/issues/9), [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#13](https://github.com/elenaatorralbo/txori-kantua/issues/13) |
| [#20 Implement Flask read API and OpenAPI specification](https://github.com/elenaatorralbo/txori-kantua/issues/20) | Backend | High | Javier | 5 | [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19) |
| [#21 Build Grafana dashboards for real environmental and bird data](https://github.com/elenaatorralbo/txori-kantua/issues/21) | Frontend | Critical | Erik | 5 | [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), [#14](https://github.com/elenaatorralbo/txori-kantua/issues/14), [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) |
| [#22 Implement presence-driven multilingual LCD station](https://github.com/elenaatorralbo/txori-kantua/issues/22) | Frontend | High | Elena | 5 | [#5](https://github.com/elenaatorralbo/txori-kantua/issues/5), [#6](https://github.com/elenaatorralbo/txori-kantua/issues/6), [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10), [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) |
| [#23 Demonstrate the complete sensor-to-dashboard pipeline](https://github.com/elenaatorralbo/txori-kantua/issues/23) | Testing | Critical | Erik | 3 | [#14](https://github.com/elenaatorralbo/txori-kantua/issues/14), [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21) |
| [#24 Monitor Raspberry Pi resources and service health](https://github.com/elenaatorralbo/txori-kantua/issues/24) | DevOps | Medium | Erik | 3 | [#2](https://github.com/elenaatorralbo/txori-kantua/issues/2), [#13](https://github.com/elenaatorralbo/txori-kantua/issues/13), [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19) |

## Sprint 3

| Issue | Área | Prioridad | Responsable propuesto | Puntos | Dependencias |
|---|---|---|---|---|---|
| [#25 Validate recognition quality and false positives](https://github.com/elenaatorralbo/txori-kantua/issues/25) | AI | High | David | 5 | [#17](https://github.com/elenaatorralbo/txori-kantua/issues/17), [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18) |
| [#26 Harden reconnection duplicate handling and degraded operation](https://github.com/elenaatorralbo/txori-kantua/issues/26) | Backend | High | Javier | 5 | [#18](https://github.com/elenaatorralbo/txori-kantua/issues/18), [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20), [#22](https://github.com/elenaatorralbo/txori-kantua/issues/22) |
| [#27 Automate contract unit and integration tests in CI](https://github.com/elenaatorralbo/txori-kantua/issues/27) | Testing | High | David | 5 | [#20](https://github.com/elenaatorralbo/txori-kantua/issues/20), [#22](https://github.com/elenaatorralbo/txori-kantua/issues/22), [#23](https://github.com/elenaatorralbo/txori-kantua/issues/23), [#26](https://github.com/elenaatorralbo/txori-kantua/issues/26) |
| [#28 Add daily aggregates and temporal dashboard statistics](https://github.com/elenaatorralbo/txori-kantua/issues/28) | Data | Medium | Erik | 3 | [#19](https://github.com/elenaatorralbo/txori-kantua/issues/19), [#21](https://github.com/elenaatorralbo/txori-kantua/issues/21) |
| [#29 Deploy systemd services and verify reboot recovery](https://github.com/elenaatorralbo/txori-kantua/issues/29) | DevOps | Critical | Javier | 5 | [#24](https://github.com/elenaatorralbo/txori-kantua/issues/24), [#26](https://github.com/elenaatorralbo/txori-kantua/issues/26) |
| [#30 Document installation reproduction and operations](https://github.com/elenaatorralbo/txori-kantua/issues/30) | Documentation | High | Erik | 3 | [#27](https://github.com/elenaatorralbo/txori-kantua/issues/27), [#29](https://github.com/elenaatorralbo/txori-kantua/issues/29) |
| [#31 Run MVP acceptance and rehearse the final demonstration](https://github.com/elenaatorralbo/txori-kantua/issues/31) | Testing | Critical | Elena | 5 | [#25](https://github.com/elenaatorralbo/txori-kantua/issues/25), [#27](https://github.com/elenaatorralbo/txori-kantua/issues/27), [#28](https://github.com/elenaatorralbo/txori-kantua/issues/28), [#29](https://github.com/elenaatorralbo/txori-kantua/issues/29), [#30](https://github.com/elenaatorralbo/txori-kantua/issues/30) |
| [#32 Publish v1.0.0 only after verified MVP acceptance](https://github.com/elenaatorralbo/txori-kantua/issues/32) | DevOps | Critical | Javier | 3 | [#31](https://github.com/elenaatorralbo/txori-kantua/issues/31) |

## Opcionales, fuera del MVP

| Issue | Área | Prioridad | Responsable propuesto | Puntos | Dependencias |
|---|---|---|---|---|---|
| [#33 Explore Euskalmet context and Leaflet nature maps](https://github.com/elenaatorralbo/txori-kantua/issues/33) | Frontend | Low | Erik | 3 | [#31](https://github.com/elenaatorralbo/txori-kantua/issues/31) |
| [#34 Explore anomaly alerts dawn chorus and period comparisons](https://github.com/elenaatorralbo/txori-kantua/issues/34) | Data | Low | Erik | 3 | [#31](https://github.com/elenaatorralbo/txori-kantua/issues/31) |

## Javier: cuenta confirmada, invitación pendiente

Cuenta verificada: [javiers2004](https://github.com/javiers2004). Responsabilidad prevista sobre #2, #9, #10, #13, #18, #19, #20, #26, #29 y #32. GitHub rechazó la comprobación de asignabilidad y el intento de asignación no añadió ningún assignee el 06/11/2026. El campo Owner = Javier y la vista Javier permiten seguir sus diez tareas mientras acepta. Después, añadirlo a Assignees sin borrar responsables existentes.

## Carga propuesta para revisar

| Responsable | Sprint 1 | Sprint 2 | Sprint 3 |
|---|---:|---:|---:|
| David | 14 | 13 | 10 |
| Javier | 13 | 16 | 13 |
| Elena | 12 | 10 | 5 |
| Erik | 5 | 11 | 6 |

Los puntos no equivalen a horas y las habilidades no son intercambiables. Erik apoyará las pruebas y el registro de hardware durante Sprint 1, revisará consultas junto a Javier en Sprint 2 y ayudará en ensayo/documentación durante Sprint 3. David y Elena compartirán validación física; todos revisarán PR ajenas. Elena confirmó el grupo el 06/11/2026; aún debe confirmarse capacidad neta antes de convertir esta previsión en compromiso.
