# Privacidad de audio y datos

## Principio de diseño

Captura e inferencia locales en Raspberry Pi. **No se almacenan grabaciones de conversaciones ni se transmite audio bruto.** Esta es una restricción a implementar y comprobar, no una garantía ya validada de software inexistente. No se hace reconocimiento de hablantes ni transcripción.

## Flujo permitido

Micrófono → ventana limitada en RAM → inferencia → metadatos de especie/confianza/tiempo → eliminación de la referencia a la ventana. El búfer se reutiliza y se limita su tamaño; no se promete borrado físico seguro de memoria administrada. No habrá archivos WAV temporales, spool de audio, volcados ni logging de muestras.

La prueba de provisión revisará swap y volcados para evitar que páginas con audio lleguen a disco: desactivar swap persistente y core dumps para captura/inferencia, verificar librerías y servicios externos, o demostrar una protección equivalente. No asumir que «usar RAM» basta. Las políticas se probarán con sonido sintético y sin grabar personas para verificar privacidad.

## Datos permitidos y minimización

Especie candidata, score, versión de modelo, tiempo de observación/recepción, estación lógica, valores ambientales y salud técnica. Ubicación aproximada para filtro puede permanecer en configuración local; no publicar coordenadas sensibles de fauna. No almacenar voces, transcripciones, identificadores de visitantes ni historiales personales de presencia. PIR/touch disparan interacción, no perfiles de personas.

Retención propuesta en ADR 007, pendiente de capacidad y revisión del equipo. Purga y backup solo de metadatos necesarios. Credenciales fuera de Git, logs rotados, permisos mínimos y acceso local por defecto. Una señal visible de la estación explicará que analiza sonidos localmente para detectar aves y no guarda audio.

## Verificación obligatoria

1. Inventariar todas las rutas de escritura, temporales, logs, cachés de librerías, swap y volcados.
2. Ejecutar captura/inferencia con sonido sintético autorizado; revisar archivos creados y datos persistidos.
3. Inspeccionar publicaciones MQTT y tráfico saliente en entorno de prueba: solo metadatos permitidos.
4. Forzar desconexión, cola llena y fallo de inferencia; comprobar que no aparece un mecanismo de grabación de emergencia.
5. Adjuntar resultados y configuración a la issue, sin audio personal. Repetir antes de aceptación del MVP.

Un corpus público autorizado sin voces puede utilizarse como fixture de evaluación externo, con origen y licencia registrados; no equivale a conservar audio capturado por la estación. Ante persistencia o transmisión accidental, detener captura, limitar acceso, eliminar los datos afectados según procedimiento del equipo, corregir y repetir pruebas antes de reiniciar.
