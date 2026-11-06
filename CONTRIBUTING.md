# Contribuir a Txori Kantua

`main` es la rama estable. Crear `feature/...`, `fix/...` o `docs/...` desde una copia actualizada de main, enlazar una issue y mantener PR pequeñas con un resultado coherente. Usar commits descriptivos; cada integrante utiliza su propia cuenta.

1. Revisar criterios, dependencias y estado del hardware. Seleccionar trabajo en planning y actualizar Project.
2. Implementar con pruebas de lógica/contrato y evidencia física donde corresponda; documentar versiones y límites.
3. Abrir PR con contexto, validación y referencias. Usar `Closes #N` únicamente cuando la PR complete todos los criterios; para avances parciales, `Refs #N`.
4. Solicitar revisión a otro miembro. Resolver observaciones antes de fusionar; no autoaprobar ni marcar Done con pruebas pendientes.
5. Tras integración, comprobar estado real y cerrar la issue si la evidencia satisface el alcance. Actualizar documentación y Project.

Evitar commits directos a main cuando exista una alternativa razonable. No se activan reglas que requieran checks inexistentes. Desde el 06/11/2026, main requiere una aprobación de otro miembro y conversaciones resueltas; nuevos cambios invalidan aprobaciones anteriores. No se permiten force-push ni borrado de main. No hay checks de CI obligatorios todavía. La administradora conserva capacidad de excepción para recuperación, aunque debe seguir el flujo de PR y revisión en el trabajo normal.

## Configuración, datos y calidad

- Nunca subir `.env` reales, tokens, claves, copias de BD ni grabaciones. Una futura `.env.example` incluirá únicamente nombres y valores ficticios.
- No instalar paquetes globalmente ni asumir versiones: usar entorno virtual y fijar dependencias que se hayan probado en Pi 5.
- Separar adaptadores físicos de lógica; validar JSON en los límites y manejar fallos de red/periféricos.
- Logs estructurados con identificadores y sin audio, credenciales o datos personales.
- Un cambio de contrato incompatible exige versión nueva y plan de migración; acordarlo con todos los consumidores.
- No inventar resultados de tests. Documentar qué se ejecutó, dónde, con qué commit y qué falta.

Todavía no hay suite de software ni comando oficial de pruebas. Cada PR que añada código introducirá su verificación reproducible; la issue de CI consolidará la automatización. No añadir archivos Python vacíos para aparentar implementación.
