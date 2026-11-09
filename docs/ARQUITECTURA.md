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
