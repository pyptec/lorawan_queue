# Reglas permanentes del proyecto

## Alcance

Gateway Raspberry Pi 4 + RAK5146/SX1303 SPI + Semtech UDP Packet Forwarder + TTN + cola local SQLite. Python; FastAPI y dashboard en fases posteriores.

## Evidencia y trazabilidad

- No inventar resultados ni afirmar funcionamiento sin evidencia directa del sistema correspondiente.
- Usar exclusivamente estos estados documentales: CONFIRMADO, PENDIENTE, HIPÓTESIS, ERROR, CORREGIDO. Son distintos de los estados de eventos pending, sent, failed.
- Cada intervención se registra en BITACORA.md con: PROMPT XXX, ROL, TAREA, FORMATO, EVIDENCIA, ARCHIVOS CONSULTADOS, ARCHIVOS MODIFICADOS, COMANDOS EJECUTADOS, RESULTADO, VALIDACIÓN, PENDIENTES, ESTADO.
- Registrar prompts recibidos, decisiones, cambios, comandos realmente ejecutados, resultados y límites de las pruebas. Identificar explícitamente los comandos sugeridos que no se ejecutaron.
- Mantener README.md, BITACORA.md, AGENTS.md y docs/. Preservar antecedentes relevantes y no sobrescribir evidencia histórica como si fuera actual.
- No publicar claves TTN, credenciales SSH, payloads sensibles ni bases de datos de producción.

## Cambios y despliegue

Antes de modificar una función existente: (1) revisar código; (2) revisar configuración; (3) consultar estado real; (4) identificar problema; (5) proponer cambio; (6) realizar cambio solo en PC; (7) commit; (8) push; (9) pull en Raspberry; (10) validar; (11) documentar. Una fase sin acceso real permanece PENDIENTE. No editar directamente funciones en Raspberry.

## Cola y protocolo

- Solo los uplinks pueden pasar por la cola persistente. Preservar payload original, timestamp original, estado, intentos, último intento y fecha de envío.
- Objetivo: pending, sent, failed; definir política de agotamiento, recuperación y reintentos antes de implementarla.
- No almacenar ni retrasar downlinks, PULL_RESP, TX_ACK, Join Accept, RX1 ni RX2. Evitar bloqueos indirectos por SQLite, esperas de ACK o drenaje de backlog.
- Un PUSH_ACK no es evidencia de entrega a integraciones. Diferenciar recepción UDP, aceptación del uplink y entrega final.
- No asumir que retransmitir datagramas antiguos a TTN recupera eventos o ventanas de recepción. Validar compatibilidad, temporización y contadores de trama.
- No sustituir silenciosamente el timestamp original; distinguir hora RF, recepción local y envío, su fuente y precisión. Auditar paquetes con múltiples rxpk.
- No asumir AU915 ni su bloque a partir de la ubicación: contrastar configuración del nodo, concentrador y TTN.

## Fases en orden

1. Documentación y bitácora.
2. Verificación del gateway.
3. Verificación de TTN.
4. Auditoría de la cola actual.
5. Prueba sin Internet.
6. Validación de reenvío.
7. Dashboard web.
8. Automatización de servicios.
9. Recuperación y reinicio.

No avanzar sin registrar el resultado de la fase anterior. Una propuesta o lectura estática no equivale a una prueba operacional.
