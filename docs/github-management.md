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
- Assignees: campo nativo; solo cuentas verificadas. Start date y Target date completados para 32 issues del MVP.
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
| Roadmap | Timeline, excluye `label:optional`; fechas en los items |

Milestones: [Foundations](https://github.com/elenaatorralbo/txori-kantua/milestone/1), 17/11/2026; [Working Pipeline](https://github.com/elenaatorralbo/txori-kantua/milestone/2), 03/12/2026; [MVP Release](https://github.com/elenaatorralbo/txori-kantua/milestone/3), 11/12/2026. La API registra 22:59:59 UTC, equivalente al final del día en Europe/Madrid para estas fechas.

## Permisos y límites

El primer acceso a Projects falló por ausencia de `read:project`/`project` en el token. Después de actualizar la autorización, se pudo crear y configurar el proyecto. No se guardaron tokens en archivos ni se alteraron permisos de colaboradores.

La ordenación persistente se configuró mediante el endpoint REST de creación de vistas, porque la entrada GraphQL de configuración de vistas solo exponía campos visibles. Referencia: [API oficial de vistas de GitHub](https://docs.github.com/en/rest/projects/views). Se sustituyó únicamente la vista inicial creada durante esta sesión, conservando una sola Product Backlog.

**Ajuste visual pendiente:** abrir Roadmap → View options → Date fields y confirmar `Start date` / `Target date` (o el campo Sprint si se prefiere representar iteraciones). La API utilizada crea el layout y carga las fechas de los items, pero no expone ni permite verificar el par de campos elegido por la interfaz. No se afirma que las barras estén ya configuradas visualmente.

No se activaron protecciones de rama ni checks obligatorios: no existe CI todavía y se evita bloquear contribuciones. La norma de revisión ajena está en CONTRIBUTING. Tras validar CI, el equipo puede añadir una aprobación obligatoria y solo checks existentes, comprobando permisos y excepciones antes de activar. No hay release ni tag anticipado.

Un Project personal no hereda automáticamente todos los permisos de escritura del repositorio. No se han añadido colaboradores al Project, para respetar la instrucción de no modificar permisos sin necesidad. La propietaria puede gestionar los campos; verificar con el equipo si requiere acceso de edición antes de invitar las cuentas confirmadas en Project → Settings → Manage access. Ver y asignar issues en el repo no equivale a poder editar campos del Project.

## Wiki

`has_wiki` está activo, pero `git ls-remote https://github.com/elenaatorralbo/txori-kantua.wiki.git` devolvió «Repository not found». No se ha creado ni publicado ninguna página. La documentación canónica se conserva en la PR del repositorio para evitar dos copias divergentes.

Si se quiere habilitar una portada de Wiki:

1. Abrir [Wiki](https://github.com/elenaatorralbo/txori-kantua/wiki) con cuenta con escritura y seleccionar **Create the first page**.
2. Crear `Home` con título Txori Kantua y enlaces a README, arquitectura, hardware, SCRUM, roadmap, MQTT, API y privacidad de `main`, una vez fusionada la PR.
3. Añadir navegación `_Sidebar` con esos mismos enlaces y un enlace al Project.
4. Mantener las páginas como índice; los cambios de contenido técnico se revisan por PR en `docs/`.

## Pendientes reales

- Revisión y fusión de la PR documental por otro miembro.
- Comprobar campos de fecha de Roadmap en la interfaz.
- Confirmar username de Javier y composición de grupo con el profesor.
- Confirmar disponibilidad/capacidad del equipo y material; ninguna prueba física se ha ejecutado.
- Inicializar Wiki solo si aporta valor; no bloquea el proyecto.
- Revisar acceso de edición al Project si el equipo va a mover tarjetas directamente.
