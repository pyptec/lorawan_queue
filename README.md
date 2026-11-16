# Gateway LoRaWAN: Raspberry Pi 4 + RAK5146 SPI

## Estado y alcance

FASE 1: estructura documental preparada. Operación del gateway: PENDIENTE de verificación en Raspberry Pi. Este repositorio contiene un proxy Semtech UDP en Python con SQLite; no demuestra por sí solo que la recepción RF, TTN o los reenvíos funcionen.

Código base revisado: `a4a4cd64ae7096936fd02d897ac8e57ee5ad7e2e`, rama `main`. La versión anterior del README se conserva en [docs/README_PREVIO.md](docs/README_PREVIO.md) como antecedente; sus afirmaciones operativas no constituyen pruebas.

## Documentación

- [Bitácora y registro de intervenciones](BITACORA.md).
- [Reglas permanentes](AGENTS.md).
- [Arquitectura, requisitos y diferencias actuales](docs/ARQUITECTURA.md).
- [Plan por fases y verificaciones](docs/PLAN_VALIDACION.md).
- [Fuentes oficiales](docs/FUENTES.md).

## Instalación reproducible: procedimiento pendiente de ejecución

1. Registrar modelo de Raspberry Pi, sistema operativo, revisión del RAK5146, HAT, conexión SPI, alimentación, antena y repositorio/commit instalado. No transmitir sin verificar hardware y antena.
2. Usar el [repositorio oficial RAKWireless](https://github.com/RAKWireless/rak_common_for_gateway) y su [guía oficial](https://docs.rakwireless.com/Knowledge-Hub/Learn/Raspberry-Pi-and-RAK-LPWAN-Concentrators/). Registrar el commit seleccionado y seguir las instrucciones correspondientes al hardware y sistema reales. No ejecutar el instalador sobre el gateway operativo antes de revisar su configuración y respaldo.
3. Verificar SPI, servicio del packet forwarder y configuración efectiva. Identificar AU915 y el bloque exacto de los dispositivos; todavía no se conoce ese bloque. No asumir una subbanda.
4. Verificar EUI, registro del gateway, cluster TTN, plan de frecuencias y eventos en la consola. No deducir conectividad por el hostname configurado.
5. Solo después de las verificaciones, evaluar el proxy y su despliegue. Conservar un respaldo de configuración y base de datos antes de cambios.

## Configuración observada en el código

| Parámetro | Valor local observado |
|---|---|
| Escucha | `127.0.0.1:1700` |
| Destino | `nam1.cloud.thethings.network:1700` |
| SQLite | `/home/pi/lorawan_queue/lorawan_queue.db` |
| Espera ACK | 2 segundos |
| Lote | 10 paquetes |
| Espera sin pendientes | 5 segundos |
| Reintento | pausas de 60 segundos en el worker |

La constante `RETRY_INTERVAL` existe, pero las pausas de fallo usan literalmente `60`. Estos valores describen el archivo local, no la configuración activa de la Raspberry.

El programa utiliza la biblioteca estándar de Python. Comando de arranque previsto en Raspberry, no ejecutado en esta intervención:

```bash
python3 lorawan_queue.py
```

El módulo abre sockets al importarse; no importarlo para comprobar sintaxis. No se ha instalado ni validado un servicio systemd. FastAPI y dashboard corresponden a fases posteriores.

## Operación y límites actuales

Se conserva el datagrama recibido en `raw_packet`; el worker modifica `rxpk[].time` en la copia enviada. Solo hay transiciones implementadas a `pending` y `sent`. `failed` es un requisito pendiente. `sent` significa que el programa recibió un PUSH_ACK con token coincidente; no prueba entrega a la aplicación final.

No se promete recuperación completa mediante reenvío UDP tardío. La aceptación por TTN, los contadores de trama y la entrega final requieren pruebas. Conservar `time` no recupera ventanas RX1/RX2 vencidas. Los Join Request y mensajes que requieren respuesta inmediata necesitan tratamiento explícito en la auditoría.

Desde PROMPT 004, el receptor no espera ACK remoto de estadísticas: las delega a stat_worker mediante una cola acotada no bloqueante. Aún realiza escrituras SQLite para uplinks; ausencia de retardos global y latencia real PENDIENTES. Ver [arquitectura](docs/ARQUITECTURA.md).

## Flujo de cambios

Revisar código, configuración y estado real; identificar el problema; proponer cambio; modificar solo en el PC; validar localmente; commit; push; pull en Raspberry; validar allí; registrar evidencia. No registrar pasos pendientes como ejecutados. No modificar funciones existentes antes de reunir la evidencia requerida.

## PROMPT 003: preparación de activación controlada (registro de esa revisión)

Servicio preparado en [deploy/lorawan-queue.service](deploy/lorawan-queue.service), todavía sin instalar. Se conserva íntegramente lorawan_queue.py. `LOCAL_HOST` no existe: el nombre utilizado es `LOCAL_IP = "127.0.0.1"`.

Estado comunicado por el usuario al abrir PROMPT 003, atribuido a PROMPT 002: Packet Forwarder directo a `nam1.cloud.thethings.network:1700`; cola inactiva; proxy UDP sin escucha; SQLite con 58 eventos históricos `sent`; Uvicorn :8080 pertenece a `ttn_iotrack_receiver.py`. No son mediciones de esta sesión: los intentos SSH del asistente fueron rechazados. Los 58 eventos no prueban recepción o reenvío actuales.

### Revisión de arquitectura

CONFIRMADO por lectura local: `local_receiver` persiste PUSH_DATA con rxpk como pending antes del ACK local. `queue_worker` consulta FIFO, modifica la copia temporal, incrementa intentos, envía a TTN y espera PUSH_ACK con token coincidente; solo entonces `mark_sent` registra sent. Sin ACK permanece pending y espera 60 s. No hay transición failed.

CONFIRMADO por lectura local: PULL_DATA y TX_ACK se envían por down_socket sin cola; downstream_receiver reenvía PULL_ACK y PULL_RESP al último cliente PULL_DATA sin SQLite ni espera de PUSH_ACK. PENDIENTE: garantizar latencia, pues local_receiver comparte recepción con persistencia y espera síncrona de estadísticas, y el worker puede esperar hasta 5 s sin pendientes. Preparar esta unidad no resuelve esos bloqueos ni garantiza Join Accept/RX1/RX2. Revisar y validar antes de cambiar el destino del forwarder.

### Despliegue manual futuro (NO ejecutado)

Tras completar revisión, commit y push en PC, usar Raspberry solo para pull, instalación, ejecución y validación. No hacer git add/commit/push allí. Identificar primero unidad real del forwarder, archivo JSON efectivo, estado Git, procesos, permisos y ocupación UDP 1700. No lanzar otra instancia manual del proxy: el código usa SO_REUSEADDR y no garantiza exclusividad de puerto.

En Raspberry, con árbol limpio y desde el repositorio correcto, el despliegue previsto es:

```bash
cd /home/pi/lorawan_queue
git status --short
git pull --ff-only
# Si .venv no existe, crear el entorno; no reemplazar uno existente sin revisarlo.
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/python3 -m py_compile lorawan_queue.py
```

Verificar ejecutable `/home/pi/lorawan_queue/.venv/bin/python3`, lectura del script y permisos del usuario pi para el directorio, la DB existente y sus archivos auxiliares. Conservar respaldo consistente de SQLite y de la configuración efectiva del forwarder; no copiar solo el .db de una base activa en WAL. No borrar ni reinicializar los 58 registros. El arranque ejecuta init_db y puede añadir columnas/índice si faltan.

Antes de activar: revisar la limitación de latencia anterior y validar la unidad con `systemd-analyze verify deploy/lorawan-queue.service`. Solo cuando se autorice la activación real:

```bash
sudo install -m 0644 deploy/lorawan-queue.service /etc/systemd/system/lorawan-queue.service
sudo systemctl daemon-reload
sudo systemctl enable --now lorawan-queue.service
systemctl status lorawan-queue.service --no-pager
sudo ss -lunp
journalctl -u lorawan-queue.service -n 100 --no-pager
```

No se modifica automáticamente la unidad del forwarder ni se presupone su nombre o ruta. Primero verificar que el proxy está sano y escucha en 127.0.0.1:1700. Después, en una intervención autorizada, cambiar únicamente estos campos del JSON efectivo, manteniendo EUI, SPI, AU915 y canales:

```json
{
  "server_address": "127.0.0.1",
  "serv_port_up": 1700,
  "serv_port_down": 1700
}
```

El destino upstream permanece en lorawan_queue.py: `nam1.cloud.thethings.network:1700`. Aplicar la configuración mediante el procedimiento de la unidad real identificada; todavía no se autoriza ni ejecuta ese cambio. Uvicorn :8080 corresponde al receptor externo informado y no debe detenerse para liberar UDP 1700.

### Validación posterior y reversión (PENDIENTE)

Correlacionar uplink nuevo, inserción pending, intento, PUSH_ACK, sent y recepción en aplicación TTN; revisar tiempos y no confundir ACK UDP con entrega final. Verificar PULL_ACK, PULL_RESP, TX_ACK y Join Accept/RX1/RX2 con y sin tráfico pendiente; medir latencias. No hacer aún prueba de pérdida de Internet.

Si falla la activación, restaurar primero el destino y puertos anteriores del forwarder desde el respaldo y aplicar su configuración con el procedimiento verificado. Después detener/deshabilitar el proxy si corresponde. Conservar SQLite y logs; documentar todo. Ninguna instrucción de esta sección se ha ejecutado en Raspberry durante PROMPT 003.

## PROMPT 004: estadísticas fuera del receptor

CORREGIDO en el código del PC: la rama solo-stat de local_receiver podía esperar ACK_TIMEOUT=2 s en send_push_and_wait_ack, además de esperar push_lock si lo tenía el worker de uplinks. Ahora envía PUSH_ACK local, ejecuta stat_queue.put_nowait(data) y vuelve al ciclo de recepción sin esperar ACK remoto ni espacio disponible.

```text
PUSH_DATA/stat -> local_receiver -> PUSH_ACK local
                              -> stat_queue (100 datagramas, memoria)
                              -> stat_worker -> TTN/PUSH_ACK remoto
```

Si se llena, se descarta la nueva estadística y se registra `[WARN] stat_queue llena`; el ACK local ya se ha enviado. El worker espera hasta 1 s por una entrada, envía con la función ACK existente y completa la tarea incluso ante error. Las estadísticas no se persisten ni reintentan por este worker; no se garantiza su entrega y se pierden las pendientes al terminar el proceso. Se conserva el socket upstream y push_lock compartidos para evitar mezclar respuestas ACK entre workers: esa espera queda fuera del receptor y todavía puede influir en tiempos de envío de uplinks.

Uplinks rxpk, paquetes mixtos rxpk+stat, SQLite, queue_worker, tiempos, reintentos y rutas de downlink mantienen su lógica. No se afirma eliminación de toda latencia: siguen la persistencia SQLite, el intervalo ocioso y backlog de uplinks y posibles bloqueos de salida de logs/sockets. No se ha activado el servicio ni cambiado la Raspberry.

Validación reproducible en PC:

```bash
python -m py_compile lorawan_queue.py
python -m unittest discover -s tests -v
```

Las pruebas cargan solo definiciones de funciones mediante AST, con sockets y envío simulados: no importan el módulo completo, no abren UDP ni tocan SQLite/TTN. Cubren ACK remoto retenido con PULL_DATA/TX_ACK posteriores, saturación, resultados/error de envío y prioridad de rxpk en datagramas mixtos. No sustituyen pruebas de red ni temporización real en Raspberry.


## PROMPT 005: fast-path de uplinks (PC, 2026-11-11)

CORREGIDO en PC: rxpk se persiste antes del ACK local y se reserva bajo db_lock para fast_worker. Este worker despierta al recibir trabajo, envia el datagrama original por un socket conectado independiente y solo marca sent tras PUSH_ACK con token coincidente. sent acredita ACK UDP, no aceptacion LoRaWAN ni entrega a integraciones. Sin ACK/error, libera la reserva y conserva pending para queue_worker. No hay cambio de esquema ni estado sending persistente; tras reiniciar, los registros pendientes siguen recuperables.

fast_queue admite 100 entradas; si se llena, el uplink permanece en SQLite para reintento. La reserva excluye envios simultaneos; no garantiza entrega unica cuando TTN recibe pero se pierde el ACK. El worker inmediato serializa sus propios intentos: bajo carga o fallos puede existir espera entre uplinks. SQLite sigue en el receptor compartido; ausencia total de bloqueo y latencia cercana a cero requieren medicion operacional. Se mantienen politica de reintentos existente y dos definiciones historicas de get_original_time_from_rxpk (activa la segunda, fallback UTC local si diferencia >10 s).

CORREGIDO: los reintentos envian raw_packet intacto, sin inject_original_time; se preservan tmst y los distintos rxpk.time del datagrama. original_time conserva su calculo historico y no acredita siempre hora RF. Downstream y configuracion conservados. CONFIRMADO: py_compile y 12 pruebas aisladas con SQLite temporal y transporte simulado. PENDIENTE: Raspberry, TTN, OTAA, corte/restauracion de Internet y reinicio real. SSH rechazo autenticacion; no se desplego ni se ejecuto Git add/commit/push. Ver BITACORA.md, PROMPT 005.


### PROMPT 005: revision posterior

CORREGIDO: esta revision sustituye la afirmacion anterior de que ambas rutas envian bytes intactos. Solo fast_worker envia el datagrama original; queue_worker restaura inject_original_time(raw_packet, original_time) antes del envio. La DB conserva raw_packet y original_time sin modificarlos; el datagrama de reintento conserva tmst y asigna rxpk.time=original_time en ISO UTC a todos los rxpk. Se mantiene el fallback local historico de original_time, por lo que no siempre representa hora RF validada. Si fast_queue se llena, el uplink queda pending durable, pero un OTAA puede perder su ventana RX. CONFIRMADO: compilacion y 15 pruebas locales; operacion RF/TTN PENDIENTE.


## PROMPT 006 — Dashboard SAMEE LoRaWAN Gateway (2026-11-15)

Implementación local autorizada expresamente; no cierra las fases operacionales anteriores, que permanecen PENDIENTES. No se modifica lorawan_queue.py ni la base existente.

Arquitectura: proceso FastAPI separado -> muestreador compartido (pausa 5 s después de cada muestra) -> API y WebSocket (2 s). SQLite URI mode=ro y query_only, timeout de bloqueo 20 ms, presupuesto VM 80 ms, últimos 100 registros. El agregado histórico puede agotar el presupuesto: estado UNKNOWN, sin índices ni migraciones nuevos. No se usa immutable porque la base cambia. Lecturas aún pueden competir por I/O/locks; medir impacto real PENDIENTE. No se crea gateway_events.

Archivos: dashboard/app.py, queue_monitor.py, system_monitor.py, gateway_monitor.py, device_decoder.py, templates/index.html y static locales; deploy/dashboard.service; requirements.txt y requirements-dev.txt; tests/test_dashboard.py.

API GET: /api/status, /api/system, /api/queue, /api/devices, /api/gateway, /api/services. WS /ws/status comparte caché, limita envío lento y rechaza origen web distinto al host. Cuatro vistas: resumen, dispositivos, cola con marcas disponibles y sistema. No sirve BLOB, token Semtech ni payload de aplicación. Usa textContent para datos externos.

Fuentes: CPU/RAM/disco/uptime/frecuencia/interfaces psutil; temperatura sysfs Linux; servicios systemctl show con timeout; Internet TCP a 1.1.1.1:443 y resolvectl query del host TTN (aproximación, no universal; sin resolvectl DNS UNKNOWN). TTN usa último ack_at: ONLINE hasta 120 s, luego DEGRADED; falta de ACK no demuestra OFFLINE. PUSH_ACK no acredita entrega final; PULL_ACK no disponible. RAK/SPI/GPS UNKNOWN; AU915 FSB1 solo declarado, no verificado. No se consultan logs crudos ni secretos. Sent/ACK comparten marca histórica; fast-send/commit exacto no registrados. Original_time puede ser fallback local, no siempre hora RF. No se estima autonomía sin historial.

Dispositivos: ventana de 100 datagramas, hasta 64 rxpk por datagrama; extracción local de DevAddr/DevEUI, FCnt16, FPort y metadatos RF. DevAddr no identifica permanentemente; no hay asociación verificada a LILYGO/Dragino/QALCOSONIC ni claves/decoder de aplicación local, por lo que valores son NO DISPONIBLES.

Ejecución local sugerida (NO ejecutada como servidor LAN): `python -m pip install -r requirements.txt`; configurar DASHBOARD_DB_PATH hacia base autorizada; `python -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8080 --workers 1`. Abrir http://127.0.0.1:8080. Sin base muestra UNKNOWN y no la crea. Dependencias dev: `python -m pip install -r requirements-dev.txt`. Tests: `python -m unittest discover -s tests -v`.

Raspberry PENDIENTE: después de revisión, aprobación de Jaime, commit/push PC y pull Raspberry; revisar puerto 8080 (antecedente de otro receptor), intérprete/usuario/rutas, acceso de lectura DB y journal, firewall LAN y systemd-analyze verify. Unidad preparada, NO instalada. Binding 0.0.0.0 sin autenticación requiere LAN confiable y firewall; no publicar en Internet. GPS/identidades y medición RF precisan fuentes validadas. Validar CPU/I/O, cola bajo backlog, online/offline/recuperación y WebSocket real en navegador. No probar corte ni reinicio ahora.


## PROMPT 007 — Revisión técnica del dashboard (2026-11-15)

CORREGIDO respecto a PROMPT 006: muestreos independientes de sistema (5 s), cola (10 s), conectividad y servicios (15 s), con pausas después de cada lectura; WebSocket cada 2 s. Los plazos de conectividad/servicios no retrasan los datos locales. `updated_at` conserva la fecha por fuente. Las fuentes ausentes producen UNKNOWN; no se descarta el resto de métricas. CPU usa una muestra de 100 ms en un hilo separado. No se modifica el proxy.

**Datos:** lorawan_queue.db no se almacena en PC ni se versiona. La DB operacional vive únicamente en Raspberry; Git contiene código y esquema esperado. Las pruebas usan TemporaryDirectory fuera del repositorio y cierran conexiones explícitamente. No copiar producción como fixture. La ausencia de DB en PC es comportamiento correcto: HTTP 200, Queue UNKNOWN, Pending/Sent NO DISPONIBLE; no inicializa SQLite.

Internet: interfaces LAN, DNS y TCP se informan por separado. TCP tiene timeout 0.5 s; resolvectl 0.75 s. Sin resolvectl o si falla se intenta getaddrinfo del host fijo TTN en proceso Python cancelable (0.75 s). Si no hay evidencia DNS suficiente: UNKNOWN. Sin shell ni hostname proporcionado por navegador. Una prueba fallida no demuestra caída universal de Internet.

TTN: Internet ONLINE y ACK de hasta 120 s -> ONLINE; Internet ONLINE y ACK antiguo -> STALE; sin evidencia suficiente o reloj futuro -> UNKNOWN. Internet OFFLINE -> TTN OFFLINE como inferencia de las pruebas de red, no como medición UDP de TTN. PUSH_ACK acredita recepción UDP; no aceptación LoRaWAN ni entrega final de aplicación.

SQLite: conexión mode=ro y query_only, snapshot de lectura consistente; límite 100 registros y 80 ms de presupuesto de instrucciones SQLite, bloqueo 20 ms. Filtrado de tamaño BLOB antes de traerlo a Python; conexión cerrada antes de decodificar JSON/LoRaWAN. Un presupuesto VM no es un límite estricto de tiempo de I/O. Lecturas pueden competir por I/O/locks: ausencia de impacto perceptible en Raspberry permanece PENDIENTE de medición. No se crean índices, tablas ni registros. No se desactiva locking ni se usa immutable sobre DB activa. El acceso read-only no garantiza ausencia de actividad interna WAL/SHM de SQLite; la unidad protege el filesystem y una DB WAL sin auxiliares legibles debe degradar a UNKNOWN, nunca habilitar escrituras para solucionarlo.

FASE 2: integrar estadísticas actuales de packet forwarder/journal para RF/GPS con formato validado; por ahora RAK5146/SPI/GPS UNKNOWN. Registro de dispositivos, mapeo DevEUI/Device ID y decoders locales validados quedan PENDIENTES: no se implementan temperatura/humedad/volumen/valores LILYGO. Las observaciones sin asociación muestran UNKNOWN DEVICE.

La revisión de PC no autoriza despliegue ni demuestra RF, TTN o ausencia de latencia. Unidad dashboard.service preparada, no instalada. Dependencias de ejecución sin cambios en esta revisión; Playwright se instala solo en PC para pruebas, no se añade al gateway.


## PROMPT 008 — Interfaz PYP e infografía operacional (2026-11-15)

CONFIRMADO en PC: presentación clara con fondo #F5F7F8, verdes #A6CE39/#6BA425, logo original `dashboard/static/img/logo_pyp.png`, navegación lateral y cinco vistas: Dashboard, Dispositivos, Cola, Eventos y Sistema. SVG inline locales, sin CDN, fuentes remotas ni frameworks nuevos. Backend, endpoints y WebSocket conservados.

Los KPI, barras y distribución de estados se calculan exclusivamente con la API. Eventos son marcas disponibles en SQLite, no un journal añadido. RF/commit exacto/Fast Send sin marcas muestran NO DISPONIBLE; Packet Forwarder ACTIVE no acredita RF OK. La recuperación de conectividad se anuncia solo tras transición observada y con pendientes; no se afirma actividad de reenvío sin evidencia. Sin DB: UNKNOWN y conteos no disponibles, sin crearla. Sin WebSocket: muestras anteriores explícitas y estados actuales desconocidos.

Diseño responsive: flujo horizontal en escritorio, parcialmente apilado en tablet y vertical en móvil; menú plegable con logo también en header móvil, foco accesible y tablas con scroll interno. Hora mostrada desde el timestamp del backend, en America/Bogota (UTC−5). Validaciones y límites: BITACORA.md, PROMPT 008. No hay datos de demostración en el producto; las capturas con fixtures se identifican como pruebas. Sin despliegue Raspberry ni commit automático.


## PROMPT 009 - UPS HAT E (2026-11-16)

CORREGIDO en PC: telemetria UPS independiente de LoRaWAN. Registros proporcionados por el usuario (no verificados en hardware en esta intervencion): bus 1, direccion 0x2d; 0x02 estado (0x40 FAST_CHARGING, 0x80 CHARGING, 0x20 DISCHARGING, sin bits IDLE); 0x10/6 bytes VBUS mV/mA/mW; 0x20/12 bytes bateria mV, corriente signed16, porcentaje, capacidad mAh, tiempo descarga y carga min; 0x30/8 bytes cuatro celdas. Palabras little endian. Corriente >=0x8000 resta 0x10000. Valores de ejemplo solo en tests, nunca en producto.

Arquitectura: proceso FastAPI separado del proxy -> tarea UPS independiente -> proceso hijo spawn por muestra -> solo lecturas SMBus -> cache -> GET /api/ups y campo ups aditivo en /ws/status. Pausa 5 s despues de cada lectura; limite de espera 2 s incluyendo arranque, terminacion del hijo si vence y joins acotados. No se inicia otro hijo hasta finalizar la llamada. Probar coste y tiempos en Raspberry PENDIENTE; un driver Linux ininterrumpible requiere validacion operacional. Sin lecturas I2C por HTTP/frame. Inicio/fallo: UNKNOWN sin ceros de sustitucion. Navegador invalida muestras de mas de 20 s o conexion obsoleta. health general conserva sus criterios previos; UPS tiene estado visual independiente.

smbus ya existe segun el usuario; importacion opcional dentro de la lectura. No se agrega dependencia PC. PENDIENTE comprobar que el interprete de .venv usado por dashboard.service puede importar smbus y que pi tiene acceso a /dev/i2c-1; el interprete del script original puede ser distinto. No se cambia la unidad ni se instala nada.

Criterios de visualizacion, NO especificacion del fabricante: VBUS >=4000 mV PRESENT, <=1000 mV NOT_PRESENT, zona intermedia UNKNOWN (external_power null); fallo de lectura UNKNOWN. Requieren contraste con alimentacion real. Bateria >=50 OK, 20-49 WARNING, 10-19 LOW, <10 CRITICAL; celdas delta <50 OK, 50-100 WARNING, >100 ATTENTION. Solo indicadores, sin acciones. Potencia bateria CALCULADA = mV * abs(mA) / 1000. Autonomia estimada no validada: siempre NO DISPONIBLE; tiempo bruto del IC solo en vista tecnica con advertencia de valor instantaneo del fuel gauge. 65535 en tiempos se presenta null de forma conservadora, interpretacion a contrastar con hardware. Se rechazan porcentaje >100, bloques incompletos/bytes invalidos, voltajes nulos/65535, capacidad/VBUS 65535 y flags de carga contradictorios; no equivalen a validacion electrica ni a lectura atomica entre registros.

UI local PYP: KPI UPS, resumen en Estado del sistema, panel UPS / RESPALDO DE ENERGIA en Sistema, cuatro baterias CSS/SVG horizontales en escritorio y 2x2 en movil, minimo/maximo/delta. Sin CDN ni nuevas dependencias frontend. UPS ausente: UNKNOWN, sin mediciones falsas.

LIMITACIONES: autonomia no validada; sin shutdown automatico; sin escrituras a registros; potencia calculada; alimentacion externa depende de VBUS; alarmas visuales. lorawan_queue.py, DB operacional y /home/pi/UPS_HAT_E/ups.py no modificados. Operacion real, fases anteriores, TTN y ausencia de impacto operacional permanecen PENDIENTES. Sin commit/push/despliegue.


## PROMPT 013 — Alias locales de dispositivos (2026-11-16)

CONFIRMADO en PC: `config/device_aliases.json` contiene nombres, Device ID TTN, DevEUI, DevAddr opcional y descripción; sin secretos ni datos de producción. `dashboard/device_aliases.py` carga configuración una vez por muestreo de cola (pausa actual 10 s), después de cerrar SQLite; enriquece únicamente los objetos de presentación. API `/api/devices`, `/api/status` y `/ws/status` comparten la caché existente. No hay tablas, columnas, escrituras SQLite ni consultas TTN nuevas.

Identificadores observados hoy: uplink de datos -> DevAddr, FPort, FCnt16 y RF; Join Request -> DevEUI. Se extraen de `identity` del decoder existente y se exponen como `dev_addr`/`dev_eui` observados, manteniendo `identity`, `model` y metadatos originales. Device ID NO está disponible en el decoder actual; el resolver admite un `device_id` si una futura fuente confirmada lo aporta. No se descifra aplicación, reconstruye FCnt completo, aprende asociación entre Join Request y sesiones ni deduce DevAddr desde sufijo DevEUI.

Prioridad: identificador observado DevEUI, luego Device ID, luego DevAddr. Si un identificador más fuerte existe pero no tiene alias, NO se sustituye por un DevAddr histórico; queda DISPOSITIVO NO REGISTRADO. Claves duplicadas se consideran ambiguas. Nunca se identifica por FPort/RSSI/SNR/FCnt. DevAddr es de sesión: puede cambiar después de OTAA o reutilizarse. La coincidencia de DevAddr con configuración no acredita identidad física permanente; invalidar/actualizar asociación al cambiar de sesión.

Configuración inicial aportada por usuario: LILYGO T3S3 / lilygo-t3s3-test / 70B3D57ED0079EC3, sin DevAddr; Dragino LHT65N / dragino-lht65n-jaime / A84041D1B186E98A, sin DevAddr; QALCOSONIC W1 / calle3sur-103 / 8C83FC05009356D5 / DevAddr histórico 009356D5. LILYGO y Dragino pueden resolverse en Join Requests con DevEUI visible; sus uplinks de datos permanecerán sin alias si no hay asociación DevAddr confirmada. FPort 10/100 por sí solos no asignan nombre. No usar fixtures como evidencia de esas asociaciones físicas.

Campos nuevos: `name`, `registered`, `alias_match` (dev_eui/device_id/dev_addr), `description`, `alias_device_id`, `alias_dev_eui`, `alias_dev_addr`. Los campos `alias_*` son configuración, no medición observada; nunca se copian al DevEUI/Device ID observado. La UI marca '(config.)' y avisa 'Alias por DevAddr de sesión'. Sin coincidencia: DISPOSITIVO NO REGISTRADO y registered=false, conservando identificadores y RF.

Editar alias SOLO en PC -> probar -> commit/push -> pull Raspberry. Puede cambiar nombre/descripción sin tocar JS. Formato JSON: objeto `devices` lista; cada entrada requiere nombre no vacío y al menos un identificador útil. Opcionales null/ausentes admitidos. Hex EUI16/Addr8 normalizados a mayúsculas, con ':'/'-'/espacios admitidos; Device ID normalizado a minúsculas. Archivo ausente, inválido, ilegible, vacío o mal formado: sin alias, dashboard continúa. Entradas incompletas útiles se aceptan; inválidas se omiten. Límites locales 64 KiB, 256 entradas, nombre 200 caracteres, descripción 500; exceder límites de archivo/lista produce fallback. No se escribe configuración ni base desde dashboard.

UI: Nombre primero, descripción/Device ID configurado o observado, identificadores diferenciados; columna DevAddr y FPort/FCnt16/RSSI/SNR preservados. También en Dispositivos recientes. Primera columna fija al desplazar internamente la tabla; escritorio/tablet/móvil. Datos externos se insertan mediante textContent. Asociación real de los tres equipos, despliegue y no regresión operacional Raspberry PENDIENTES; código LoRaWAN y backend UPS conservados.
