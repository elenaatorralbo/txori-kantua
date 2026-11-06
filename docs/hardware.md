# Hardware: inventario y plan de validación

**Nada se considera disponible, conectado o probado por aparecer aquí.** Fecha de revisión documental: 05/11/2026. Antes de cablear, registrar referencia exacta, hoja de datos del fabricante, tensión, interfaz y compatibilidad con Pi 5. No utilizar un pinout genérico de otro modelo.

| Componente previsto | Función | Conexión por verificar | Estado | Evidencia requerida |
|---|---|---|---|---|
| Raspberry Pi 5 | Captura, inferencia y control | Fuente, refrigeración y almacenamiento adecuados al modelo | No verificado | SO, alimentación y prueba térmica |
| Micrófono USB omnidireccional | Audio local | USB, formato, canales e identificador | No verificado | Diez ventanas en RAM y prueba de desconexión |
| Grove Base Hat | Interfaz de periféricos | Header, buses y drivers compatibles | No verificado | Buses/direcciones y lectura real |
| Temperatura y humedad | Ambiente | Puerto y bus según modelo | No verificado | 30 lecturas por canal, unidades y rango |
| Barómetro | Presión | Bus, dirección y unidad según modelo | No verificado | 30 lecturas y comparación de referencia |
| Luz (añadido al diseño) | Iluminación | Analógico/digital según modelo | No verificado | Respuesta en dos condiciones; lux solo con conversión validada |
| PIR | Presencia | GPIO/puerto, nivel y estabilización | No verificado | Diez ciclos y falsos disparos |
| Touch | Interacción | GPIO/puerto y antirrebote | No verificado | Diez pulsaciones sin duplicación |
| Grove RGB LCD 16×2 | Información de aves | Bus, dirección, alimentación y caracteres | No verificado | Dos líneas, colores, apagado y reinicio |

No se asignan pines ni direcciones hasta identificar modelos. Desconectar alimentación antes de modificar cableado y revisar compatibilidad eléctrica. No suponer que todas las librerías de una Raspberry Pi anterior funcionan en Pi 5.

## Registro de prueba

Cada informe debe incluir fecha, autor, issue/PR, referencia del componente, conexión revisada, versiones de SO/librería, procedimiento, resultado esperado/observado, muestras o fotografías y limitaciones. Estados permitidos: pendiente, disponible sin probar, probado con evidencia, bloqueado. Una prueba simulada lleva la etiqueta «simulada» y no satisface la prueba física.

Elena coordina el inventario y los periféricos; Erik valida sensores ambientales con su apoyo; David valida audio y Javier coordina la provisión. Los demás revisan y ayudan con cableado y datos. Si falta material, registrar responsable de conseguirlo, fecha esperada y alternativa, sin cerrar la issue por haber escrito el procedimiento.
