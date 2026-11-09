# Arquitectura y diferencias por validar

## Objetivo

```text
Dispositivos AU915 -> RAK5146/SX1303 -> SPI -> Raspberry Pi 4
  -> Semtech UDP Packet Forwarder -> proxy local -> TTN -> integraciones
                                      |
                               cola de uplinks
                                      |
                                    SQLite
```

El trayecto de downlink debe mantenerse en vivo, independiente del almacenamiento y de los reintentos. No se encolan downlinks. Esta es una condición de aceptación, no una propiedad ya probada.

## Observaciones estáticas del código base

| Hallazgo | Evidencia local | Estado |
|---|---|---|
| pending y sent implementados; sin transición a failed | init_db, get_pending_packets, mark_sent | CONFIRMADO |
| Datagrama original persistido como BLOB | save_packet | CONFIRMADO |
| Dos definiciones del extractor temporal; prevalece la segunda | get_original_time_from_rxpk, líneas base 926 y 955 | CONFIRMADO |
| Hora RF descartada si difiere más de 10 s; precisión reducida a segundos | segunda definición del extractor | CONFIRMADO |
| Un único original_time se escribe sobre todos los rxpk de un datagrama | inject_original_time | CONFIRMADO |
| ACK al gateway posterior a save_packet para rxpk | local_receiver | CONFIRMADO |
| Estadísticas esperan ACK en el receptor local y comparten push_lock con el worker | local_receiver, send_push_and_wait_ack | CONFIRMADO |
| También se encolan PUSH_DATA genéricos sin rxpk | rama else de local_receiver | CONFIRMADO |
| Duplicación basada en hash del datagrama completo, incluido token | save_packet | CONFIRMADO |
| PULL_RESP se reenvía desde otro hilo; TX_ACK y PULL_DATA entran por receptor compartido | downstream_receiver, local_receiver | CONFIRMADO |
| sent se asigna tras PUSH_ACK con token coincidente; no se verifica origen remoto del ACK | send_push_and_wait_ack, queue_worker | CONFIRMADO |
| Posible bloqueo del tráfico sensible por espera de estadísticas, lock o SQLite | derivado del flujo anterior; latencia no medida | HIPÓTESIS |

Estos hallazgos preparan la auditoría de FASE 4; no representan su ejecución ni cierre.

## Contrato objetivo de eventos

Preservar payload/datagrama original y tiempos por evento sin sobrescritura. Distinguir timestamp RF (si existe), timestamp de recepción local, fuente del tiempo, intentos, último intento, envío y evidencia de ACK. Definir unidad de evento: un datagrama puede contener varios rxpk.

Estados previstos: pending al persistir; sent según criterio de envío documentado; failed con política explícita todavía pendiente. Definir si sent representa solo ACK UDP y cómo se verifica por separado la entrega a la integración. Mantener trazabilidad de errores y evitar duplicar entrega al perderse un ACK.

## Decisiones pendientes

- Confirmar bloque AU915, cluster TTN, EUI y configuración efectiva.
- Resolver ruta inmediata para uplinks en línea y prioridad frente a backlog, sin perder persistencia.
- Evaluar reenvío tardío con TTN y tratamiento de Join Request, uplinks confirmados y contadores.
- Definir alternativa de recuperación de datos de aplicación si TTN no acepta retransmisiones tardías; no asumir descifrado del payload en el gateway ni instalar un Network Server sin decisión documentada.
- Definir límites, backoff, expiración, failed, reinicio y capacidad de disco.
- Dashboard posterior: gateway, TTN, pending/sent/failed, último uplink, último reenvío, intentos, timestamp original y de envío. Estado desconocido cuando falte evidencia; no mostrar conexión TTN por mera conexión a Internet.

## PROMPT 003: arquitectura revisada para preparación

Estado remoto aportado por el usuario (resultado atribuido a PROMPT 002): forwarder directo a nam1.cloud.thethings.network:1700, cola inactiva, proxy sin escucha, SQLite con 58 sent históricos; :8080 es ttn_iotrack_receiver.py. CONFIRMADO como información recibida, no como medición remota del asistente. No permite cerrar validación RF/TTN.

Configuración local confirmada: LOCAL_IP (no LOCAL_HOST) 127.0.0.1; LOCAL_PORT 1700; TTN_HOST nam1.cloud.thethings.network; TTN_PORT 1700; ACK_TIMEOUT 2.0; RETRY_INTERVAL 60; DB_PATH /home/pi/lorawan_queue/lorawan_queue.db. Los sleeps de fallo usan 60 literal.

```text
PUSH_DATA/rxpk -> save_packet/commit SQLite/pending -> PUSH_ACK local
             -> queue_worker -> mark_attempt -> envío TTN -> PUSH_ACK -> sent
PULL_DATA/TX_ACK -> local_receiver -> down_socket -> TTN
PULL_ACK/PULL_RESP -> downstream_receiver -> local_socket -> forwarder
```

Las ramas de downlink no usan SQLite, push_lock ni cola. No se garantiza independencia temporal: SQLite y estadísticas bloquean el receptor compartido de PULL_DATA/TX_ACK. El drenaje FIFO y el intervalo ocioso del worker también retrasan uplinks que desencadenan downlinks. No se cambia el código en esta preparación; ausencia de retardos y operación real permanecen PENDIENTES. La unidad deploy/lorawan-queue.service usa usuario pi y el Python del .venv, sin instalarse en Raspberry. Consultar README para procedimiento y reversión.

## PROMPT 004: corrección del envío de estadísticas

Las observaciones anteriores describen el código base y las revisiones históricas hasta PROMPT 003. CORREGIDO en PC: la rama solo-stat ya no llama send_push_and_wait_ack; tras PUSH_ACK local utiliza stat_queue.put_nowait, con capacidad de 100 datagramas. Si no hay espacio descarta la nueva estadística y avisa `[WARN] stat_queue llena`.

stat_worker, iniciado como daemon junto a local_receiver, downstream_receiver y queue_worker, espera por la cola con timeout y llama a la función de envío/ACK existente. Usa task_done en finally incluso ante excepciones. No hay SQLite ni persistencia de estadísticas, ni reintento propio tras fallo. up_socket/push_lock permanecen compartidos con queue_worker; solo los workers pueden esperar ese ACK/lock, no el receptor por esta rama.

CONFIRMADO en comparación AST: salvo local_receiver y main, todas las funciones existentes mantienen su estructura, incluida persistencia y downstream_receiver. PULL_DATA/TX_ACK no pasan por stat_queue y PULL_ACK/PULL_RESP siguen directos. Paquetes mixtos rxpk+stat conservan prioridad de rxpk. Persistencia de uplinks y latencia por backlog/idle permanecen sin corregir en este prompt; operación y tiempos reales PENDIENTES.
