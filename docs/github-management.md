# Configuración de GitHub y pendientes

## Auditoría inicial · 05/11/2026

Repositorio público existente: [elenaatorralbo/txori-kantua](https://github.com/elenaatorralbo/txori-kantua). Rama única `main`, commit inicial `be33ac6`, README con título; sin issues, milestones, PR, releases ni reglas de protección. Se conservaron las etiquetas predeterminadas y los colaboradores. La carpeta local `.idea/` no se modificó y queda ignorada.

Había un Project personal sin título, número 1, sin vincular a este repositorio; se dejó intacto. No se creó ningún repositorio adicional.

## Gestión creada

[Txori Kantua — IoT Development](https://github.com/users/elenaatorralbo/projects/2), público y vinculado al repositorio.

- Status: Backlog, To do, In progress, Review, Done.
- Priority: Critical, High, Medium, Low, en ese orden.
- Sprint: campo Iteration, tres periodos oficiales (14, 16 y 8 días; fechas de revisión también en milestones).
- Area: Hardware, AI, Backend, Frontend, Data, DevOps, Documentation, Testing.
- Assignees: campo nativo; solo cuentas verificadas y admitidas por GitHub. Owner: responsable planificado (David, Javier, Elena, Erik), completado para las 34 issues. Start date y Target date completados para 32 issues del MVP.
- 34 issues abiertas, sin duplicados por título ni entregable; 32 en milestones y 2 opcionales sin compromiso de sprint. Todas se incorporan en Backlog.
- 13 etiquetas añadidas: cuatro `priority:*`, ocho `area:*` y `optional`; etiquetas existentes conservadas.

| Vista | Configuración |
|---|---|
| Product Backlog | Tabla, todas las issues, Priority ascendente según orden de opciones |
| Kanban | Board, columnas Status |
| Sprint 1 | Board, `sprint:"Sprint 1"`, columnas Status |
| Sprint 2 | Board, `sprint:"Sprint 2"`, columnas Status |
| Sprint 3 | Board, `sprint:"Sprint 3"`, columnas Status |
| My Tasks | Tabla, `assignee:@me` |
| Javier | Tabla, `owner:Javier`; diez tareas, también asignadas a javiers2004 |
| Roadmap | Timeline, excluye `label:optional`; fechas en los items |

Milestones: [Foundations](https://github.com/elenaatorralbo/txori-kantua/milestone/1), 17/11/2026; [Working Pipeline](https://github.com/elenaatorralbo/txori-kantua/milestone/2), 03/12/2026; [MVP Release](https://github.com/elenaatorralbo/txori-kantua/milestone/3), 11/12/2026. La API registra 22:59:59 UTC, equivalente al final del día en Europe/Madrid para estas fechas.

## Permisos y límites

El primer acceso a Projects falló por ausencia de `read:project`/`project` en el token. Después de actualizar la autorización, se pudo crear y configurar el proyecto. No se guardaron tokens en archivos ni se alteraron permisos de colaboradores.

La ordenación persistente se configuró mediante el endpoint REST de creación de vistas, porque la entrada GraphQL de configuración de vistas solo exponía campos visibles. Referencia: [API oficial de vistas de GitHub](https://docs.github.com/en/rest/projects/views). Se sustituyó únicamente la vista inicial creada durante esta sesión, conservando una sola Product Backlog.

**Ajuste visual pendiente:** abrir Roadmap → View options → Date fields y confirmar `Start date` / `Target date` (o el campo Sprint si se prefiere representar iteraciones). La API utilizada crea el layout y carga las fechas de los items, pero no expone ni permite verificar el par de campos elegido por la interfaz. No se afirma que las barras estén ya configuradas visualmente.

Actualización 06/11/2026: main tiene protección con una aprobación obligatoria, invalidación de revisiones tras cambios y resolución de conversaciones. Force-push y borrado están deshabilitados; no se exigen checks de CI inexistentes ni CODEOWNERS. La administradora conserva excepción de recuperación (`enforce_admins=false`), manteniendo la norma de PR revisada. La API aceptó y devolvió la configuración. No hay release ni tag anticipado.

Un Project personal no hereda automáticamente todos los permisos de escritura del repositorio. No se han añadido colaboradores al Project, para respetar la instrucción de no modificar permisos sin necesidad. La propietaria puede gestionar los campos; verificar con el equipo si requiere acceso de edición antes de invitar las cuentas confirmadas en Project → Settings → Manage access. Ver y asignar issues en el repo no equivale a poder editar campos del Project.

## Wiki

`has_wiki` está activo, pero `git ls-remote https://github.com/elenaatorralbo/txori-kantua.wiki.git` devolvió «Repository not found». No se ha creado ni publicado ninguna página. La documentación canónica se conserva en la PR del repositorio para evitar dos copias divergentes.

Si se quiere habilitar una portada de Wiki:

1. Abrir [Wiki](https://github.com/elenaatorralbo/txori-kantua/wiki) con cuenta con escritura y seleccionar **Create the first page**.
2. Crear `Home` con título Txori Kantua y enlaces a README, arquitectura, hardware, SCRUM, roadmap, MQTT, API y privacidad de `main`, una vez fusionada la PR.
3. Añadir navegación `_Sidebar` con esos mismos enlaces y un enlace al Project.
4. Mantener las páginas como índice; los cambios de contenido técnico se revisan por PR en `docs/`.

## Seguimiento del 06/11/2026

La PR #35 está fusionada (commit `aac6515`). Elena confirmó el grupo de cuatro; se registra como confirmación del equipo. Javier corresponde al perfil `javiers2004` (Javier Santamaría Pascual). Tras aceptar la invitación, la comprobación de asignabilidad tuvo éxito y las diez issues #2, #9, #10, #13, #18, #19, #20, #26, #29 y #32 quedaron asignadas nativamente a su cuenta el 06/11/2026. Owner = Javier coincide con esa responsabilidad.

Se intentó configurar Roadmap desde Dia. La sesión no permite ejecutar JavaScript de automatización; los controles de accesibilidad no produjeron cambios y la captura de pantalla falló. Elena indicó que habilitar el acceso requeriría reiniciar la terminal. Por ello, las fechas de items sí están cargadas, pero la selección visual de campos sigue pendiente. No se alteraron las opciones del navegador ni se reinició la sesión.

## Pendientes reales

- Revisar la PR de seguimiento documental; la PR inicial #35 ya está fusionada.
- Comprobar campos de fecha de Roadmap en la interfaz.
- Confirmar disponibilidad/capacidad del equipo y material; ninguna prueba física se ha ejecutado.
- Inicializar Wiki solo si aporta valor; no bloquea el proyecto.
- Revisar acceso de edición al Project si el equipo va a mover tarjetas directamente.
