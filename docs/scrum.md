# SCRUM y colaboración

## Marco académico

El proyecto supone el 65 % de la asignatura. Se utiliza exclusivamente el calendario oficial de **tres sprints**. Inicio administrativo: 03/11/2026; esta preparación comienza el 05/11, por lo que no se atribuye trabajo completado a los días anteriores.

| Sprint | Intervalo | Revisión / entrega | Sprint Goal |
|---|---|---|---|
| 1 — Foundations | 03/11–17/11 | 17/11 | Reducir riesgos de hardware, fijar contratos y preparar integración |
| 2 — Working Pipeline | 17/11–03/12 | 03/12 | Mostrar un sensor físico hasta un dashboard con datos persistidos |
| 3 — MVP Release | 03/12–11/12 | Entrega 11/12 | Integrar aves, interacción, datos y recuperación con evidencia |

Las fechas compartidas son días de revisión y transición, no dos jornadas de capacidad. En Projects las iteraciones se modelan [inicio, siguiente inicio); el cierre de revisión se conserva en milestones y Target date. Demostración final durante la semana del 14/12, sin tratar esa semana como plazo adicional de desarrollo.

## Equipo y cuentas

| Persona | Responsabilidad propuesta | Cuenta comprobada | Asignación inicial |
|---|---|---|---|
| David Fernández | Scrum Master; audio y BirdNET; apoyo calidad | `DavidFernandezUD`, perfil David Fernández Fernández y acceso write | Audio, AI, coordinación y pruebas |
| Javier Santamaría | Product Owner; MQTT, API y datos; provisión | `javiers2004`, perfil Javier Santamaría Pascual; invitación pendiente | Diez issues con Owner = Javier; Assignees espera aceptación |
| Elena Torralbo | Sensores de interacción, LCD y experiencia | `elenaatorralbo`, perfil Elena Torralbo y admin | Hardware, estación y documentación |
| Erik Eguskiza | Dashboard, open data y monitorización | `eeguskiza`, perfil Erik Eguskiza Aranda y write | Sensores ambientales, dashboard, observabilidad y reproducción |

Verificación inicial mediante perfiles y colaboradores el 05/11/2026; Javier se verificó mediante su perfil e invitación el 06/11/2026. `dieguich` no es la cuenta identificada de Javier: no se le asignan tareas ni se cambian sus permisos. Las responsabilidades son propuestas, no compromisos de disponibilidad confirmados.

**Grupo confirmado por Elena el 06/11/2026:** se mantiene el equipo de cuatro. El requisito de 2–3 del enunciado se conserva como antecedente; la confirmación registrada procede del equipo, sin inventar un acta o una respuesta del profesor. Falta confirmar capacidad neta por persona en planning.

## Ritmo de trabajo

- Planning al inicio: confirmar capacidad neta, dependencias y criterios; seleccionar un compromiso realista.
- Daily breve (10 minutos, síncrono o escrito): avance, siguiente paso y bloqueo. Escalar bloqueos de hardware el mismo día.
- Refinement dos veces por semana: priorizar por valor/riesgo, aclarar criterios y actualizar estimaciones.
- Review el 17/11 y 03/12; aceptación final 11/12: mostrar comportamiento y evidencia, no solo diapositivas.
- Retrospectiva tras cada revisión: una mejora concreta, responsable y seguimiento.

Estimaciones iniciales de 3 o 5 puntos son relativas y deben revisarse, no son horas ni una velocidad histórica. Dividir una issue solo si el entregable resulta inabarcable; mantener criterios y dependencias al dividir. El dashboard y la persistencia pueden iniciarse con fixtures claramente marcados, pero solo datos físicos cumplen la revisión del Sprint 2.

## Tablero y políticas

`Backlog → To do → In progress → Review → Done`.

- Backlog: trabajo identificado, sin compromiso de ejecución inmediata.
- To do: seleccionado en planning, dependencias y material disponibles.
- In progress: una issue activa por persona como objetivo; colaboración puntual permitida.
- Review: PR abierta con pruebas y criterios cumplidos, revisión por otro miembro.
- Done: criterios comprobados, documentación actualizada y PR integrada. Cerrar issue solo con evidencia.

Las 34 issues nuevas se crean en **Backlog**. El campo **Owner** identifica al responsable planificado incluso si su acceso está pendiente; **Assignees** conserva la asignación efectiva de GitHub. La vista Javier filtra `owner:Javier` y muestra sus diez tareas. El milestone y la iteración indican previsión, no estado de ejecución. Los bloqueos se anotan con causa, dependencia y siguiente acción; no se marca Done para mejorar métricas.

## Definition of Ready / Done

Ready: finalidad, responsable propuesto, criterios verificables, contratos necesarios, dependencias y estimación discutida. Done: alcance funcional (o decisión documentada en tareas de investigación), revisión de otro miembro, pruebas con evidencia, documentación al día y PR integrada. La infraestructura física requiere evidencia de hardware; tests simulados no la sustituyen.

Seguimiento: avance por criterios y objetivos, trabajo bloqueado, tiempo en Review y riesgos. No comparar productividad personal por número de commits o puntos. Cada integrante utiliza su propia cuenta y comprende la arquitectura completa.
