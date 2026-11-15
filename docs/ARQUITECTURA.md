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


## PROMPT 005: ruta inmediata y reserva (2026-11-11)

CORREGIDO en PC respecto a los antecedentes: local_receiver/rxpk -> save_packet/commit pending -> reserva in_flight + fast_queue bajo db_lock -> ACK local. fast_worker -> mark_attempt -> socket propio conectado -> envio de bytes originales -> PUSH_ACK/token -> mark_sent; sin ACK o excepcion conserva pending. finally libera reserva. Cola inmediata acotada a 100; saturacion conserva pending y libera reserva para queue_worker. La publicacion en memoria ocurre despues del commit; reiniciar pierde solo reservas/avisos, no el registro SQLite.

queue_worker revalida pending y reclama bajo el mismo db_lock antes de enviar; evita tanto concurrencia como reenvio por snapshots anteriores ya enviados. No mantiene db_lock durante espera de ACK. Su socket/push_lock compartido con stat_worker no afecta al socket inmediato. Downstream sin cambios funcionales. Una reserva es exclusion dentro del proceso, no garantia exactly-once ante ACK perdido o reinicio tras envio. No se agrega failed, agotamiento ni otra politica de reintentos.

Ambas rutas envian raw_packet sin modificar tmst ni rxpk.time; se deja inject_original_time definido sin uso y ambas definiciones get_original_time_from_rxpk intactas. La segunda sigue activa: usa solo el primer rxpk y fallback local si diferencia >10 s. sent_at y ack_at conservan la misma hora de confirmacion; delay_seconds conserva precision entera y fuente historica de original_time. No se mide aqui el instante exacto sendto ni la hora RF por rxpk. SQLite en receptor y serializacion de intentos inmediatos siguen siendo limites temporales PENDIENTES de medicion.


### PROMPT 005: revision posterior de trazabilidad temporal

CORREGIDO respecto al texto anterior: fast_worker mantiene raw_packet intacto; queue_worker reconstruye exclusivamente el datagrama de salida mediante inject_original_time(raw_packet, original_time). Conserva tmst, cabecera y demas campos; asigna la misma hora ISO UTC a todos los rxpk. Los bytes y tiempos almacenados en SQLite no cambian. No reconstruye ventanas RX historicas ni acredita aceptacion de reenvios antiguos por TTN. La funcion y sus limitaciones previas se conservan sin refactorizacion. Saturacion de fast_queue: pending durable y reserva liberada; la ventana de un JoinAccept puede expirar antes del reintento.


## PROMPT 006 — Dashboard SAMEE LoRaWAN Gateway (2026-11-15)

Implementación local autorizada expresamente; no cierra las fases operacionales anteriores, que permanecen PENDIENTES. No se modifica lorawan_queue.py ni la base existente.

Arquitectura: proceso FastAPI separado -> muestreador compartido (pausa 5 s después de cada muestra) -> API y WebSocket (2 s). SQLite URI mode=ro y query_only, timeout de bloqueo 20 ms, presupuesto VM 80 ms, últimos 100 registros. El agregado histórico puede agotar el presupuesto: estado UNKNOWN, sin índices ni migraciones nuevos. No se usa immutable porque la base cambia. Lecturas aún pueden competir por I/O/locks; medir impacto real PENDIENTE. No se crea gateway_events.

Archivos: dashboard/app.py, queue_monitor.py, system_monitor.py, gateway_monitor.py, device_decoder.py, templates/index.html y static locales; deploy/dashboard.service; requirements.txt y requirements-dev.txt; tests/test_dashboard.py.

API GET: /api/status, /api/system, /api/queue, /api/devices, /api/gateway, /api/services. WS /ws/status comparte caché, limita envío lento y rechaza origen web distinto al host. Cuatro vistas: resumen, dispositivos, cola con marcas disponibles y sistema. No sirve BLOB, token Semtech ni payload de aplicación. Usa textContent para datos externos.

Fuentes: CPU/RAM/disco/uptime/frecuencia/interfaces psutil; temperatura sysfs Linux; servicios systemctl show con timeout; Internet TCP a 1.1.1.1:443 y resolvectl query del host TTN (aproximación, no universal; sin resolvectl DNS UNKNOWN). TTN usa último ack_at: ONLINE hasta 120 s, luego DEGRADED; falta de ACK no demuestra OFFLINE. PUSH_ACK no acredita entrega final; PULL_ACK no disponible. RAK/SPI/GPS UNKNOWN; AU915 FSB1 solo declarado, no verificado. No se consultan logs crudos ni secretos. Sent/ACK comparten marca histórica; fast-send/commit exacto no registrados. Original_time puede ser fallback local, no siempre hora RF. No se estima autonomía sin historial.

Dispositivos: ventana de 100 datagramas, hasta 64 rxpk por datagrama; extracción local de DevAddr/DevEUI, FCnt16, FPort y metadatos RF. DevAddr no identifica permanentemente; no hay asociación verificada a LILYGO/Dragino/QALCOSONIC ni claves/decoder de aplicación local, por lo que valores son NO DISPONIBLES.

Ejecución local sugerida (NO ejecutada como servidor LAN): `python -m pip install -r requirements.txt`; configurar DASHBOARD_DB_PATH hacia base autorizada; `python -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8080 --workers 1`. Abrir http://127.0.0.1:8080. Sin base muestra UNKNOWN y no la crea. Dependencias dev: `python -m pip install -r requirements-dev.txt`. Tests: `python -m unittest discover -s tests -v`.

Raspberry PENDIENTE: después de revisión, aprobación de Jaime, commit/push PC y pull Raspberry; revisar puerto 8080 (antecedente de otro receptor), intérprete/usuario/rutas, acceso de lectura DB y journal, firewall LAN y systemd-analyze verify. Unidad preparada, NO instalada. Binding 0.0.0.0 sin autenticación requiere LAN confiable y firewall; no publicar en Internet. GPS/identidades y medición RF precisan fuentes validadas. Validar CPU/I/O, cola bajo backlog, online/offline/recuperación y WebSocket real en navegador. No probar corte ni reinicio ahora.


## PROMPT 007 — Correcciones de aislamiento y evidencia

CORREGIDO: cuatro tareas de muestreo independientes publican en la misma caché del proceso ASGI: sistema 5 s, SQLite 10 s, servicios e Internet 15 s (intervalo posterior a lectura). Solo un worker Uvicorn; aumentar workers duplica muestreos. API y WS no consultan SQLite. Cada fuente mantiene `updated_at`. Los errores se aíslan por métrica y fuente; no bloquean al proxy ni eliminan las muestras de otras fuentes. Se añade DNS cancelable sin depender de resolvectl. TTN distingue ONLINE/STALE/UNKNOWN/OFFLINE con las reglas actuales de README.

SQLite mode=ro/query_only, transacción de lectura consistente, timeout 20 ms y presupuesto VM 80 ms; máximo 100 registros y 64 rxpk por datagrama. La conexión se cierra antes de decodificar. No se modifica lorawan_queue.py, no se importan sus sockets, no hay migración ni escritura de aplicación. El agregado histórico aún recorre registros y puede agotar el presupuesto; UNKNOWN explícito. Presupuesto VM no limita estrictamente I/O; medir en Raspberry con backlog antes de afirmar ausencia de impacto. La unidad mantiene filesystem protegido. No usar nolock/immutable para evitar problemas con bases activas; WAL/SHM requieren compatibilidad y permisos de lectura durante despliegue.

DB operacional exclusivamente en Raspberry; no se copia a PC ni a Git. Las fixtures son ficticias y temporales fuera del repositorio. GPS, hardware y decoders de aplicación quedan para FASE 2 del dashboard; no se identifica un modelo a partir de DevAddr sin registro validado. La vista informa UNKNOWN DEVICE y FCnt de 16 bits, no reconstruye el contador completo.
