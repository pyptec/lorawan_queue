# Plan de validación

## Registro de fases

| Fase | Resultado registrado | Estado |
|---|---|---|
| 1 Documentación | Estructura y enlaces validados; commit a056dd7 publicado; ver BITACORA.md | CONFIRMADO |
| 2 Gateway | Sin acceso ni evidencia remota | PENDIENTE |
| 3 TTN | Sin acceso ni eventos observados | PENDIENTE |
| 4 Cola | Hallazgos preliminares estáticos; auditoría no iniciada | PENDIENTE |
| 5 Sin Internet | No ejecutada | PENDIENTE |
| 6 Reenvío | No ejecutada | PENDIENTE |
| 7 Dashboard | No implementado | PENDIENTE |
| 8 Servicios | No desplegados ni inspeccionados | PENDIENTE |
| 9 Recuperación | No ejecutada | PENDIENTE |

## Evidencia requerida y criterios

1. Documentación: enlaces locales válidos, bitácora, reglas y plan; revisar diff, commit y push. Registrar su resultado antes de abrir FASE 2.
2. Gateway: modelo/OS, revisión hardware, SPI, alimentación, antena, commit RAK instalado, servicio real y logs. Registrar configuración activa, EUI y bloque AU915 cotejado con los nodos. Resultado: concentrador inicia y recibe RF con evidencia.
3. TTN: registro y cluster correctos, configuración coincidente, uplink observado en gateway y aplicación, downlink y Join Accept de control con tiempos y TX_ACK. Distinguir recepción UDP de entrega final.
4. Cola: inspeccionar esquema real en modo lectura, estados, tiempos por rxpk, deduplicación, fallos y concurrencia. Proponer cambios solo tras contrastar código/configuración/estado. Validar en PC antes de commit/push/pull y prueba remota.
5. Sin Internet: prueba acotada y reversible con acceso local disponible; documentar método de corte y restauración. Medir eventos emitidos/recibidos/guardados; payload y timestamp intactos. No ejecutar cortes desde esta fase documental.
6. Reenvío: restaurar red; correlacionar registros SQLite, ACK UDP y eventos de aplicación con identificador/conteo. Verificar timestamps, duplicados, pérdidas, contadores y comportamiento de Join Request. Un ACK aislado no basta. Medir downlinks durante backlog.
7. Dashboard: verificar cada métrica contra DB/logs y representar estados desconocidos. Definir seguridad de acceso antes de exponer FastAPI.
8. Servicios: revisar unidades existentes, usuario, permisos, rutas, orden de arranque, reinicios, logs y sincronización horaria. Documentar instalación y reversión.
9. Recuperación: reinicio del proceso y de Raspberry con pendientes; comprobar integridad SQLite, conservación temporal, recuperación y espacio en disco. Registrar límites y pérdidas si existen.

## Comandos sugeridos para Raspberry (NO ejecutados)

Primero identificar usuario, rutas y nombres de servicios; no asumir que el servicio se llama como el ejemplo.

```bash
hostnamectl
cat /etc/os-release
uname -a
ls -l /dev/spidev*
timedatectl status
systemctl list-units --type=service --all
systemctl list-unit-files --type=service
```

Después consultar la unidad identificada con `systemctl cat <unidad>` y `journalctl -u <unidad> --no-pager -n 100`; registrar exit codes y salidas pertinentes, sin secretos. Revisar `git status`, `git rev-parse HEAD` y configuración efectiva en las rutas identificadas. No ejecutar instaladores, cambiar región o reiniciar servicios durante una inspección.

## Plantilla de prueba

Fecha/zona; fase; objetivo; PC/Raspberry/TTN; versiones y commit; configuración relevante; condiciones iniciales; comando exacto; salida/exit code; resultado esperado y obtenido; artefactos; limitaciones; pendientes; estado permitido. No usar capturas simuladas como evidencia.

## PROMPT 003: preparación local y puerta de activación

La petición actual autoriza preparar la unidad antes de las fases operativas completas. No cierra automáticamente las verificaciones anteriores. Estado comunicado por el usuario para PROMPT 002: forwarder directo a TTN, cola inactiva, sin escucha del proxy y 58 sent históricos; Uvicorn :8080 es otro receptor. Evidencia remota bruta no disponible en esta sesión; verificaciones directas PENDIENTES.

- CONFIRMADO: revisión estática de constantes, persistencia, ACK local, worker y ramas directas del protocolo; sin cambios de Python.
- PENDIENTE antes de activar: resolver o medir bloqueos del receptor por SQLite/estadísticas y demora de uplinks por FIFO/idle; no afirmar cumplimiento de RX1/RX2 por tener hilo downstream.
- Validación en PC requerida antes de commit: `python -m py_compile lorawan_queue.py`, revisión estática de unidad/rutas y `git diff --check`. La compilación escribe únicamente cache local; no importa el módulo ni abre sockets.
- PENDIENTE en Raspberry: pull, existencia del intérprete .venv, permisos y respaldo SQLite, revisión de unidad con systemd-analyze, instalación autorizada y escucha UDP, cambio manual del JSON efectivo, validación de uplinks/TTN y downlinks. Consultar README.
- No ejecutar en esta intervención instalación, reinicios, cambio del forwarder o corte de Internet. El servicio web existente :8080 no forma parte del proxy.

## PROMPT 004: pruebas de aislamiento de estadísticas

CONFIRMADO en PC: py_compile código 0; cuatro pruebas unittest correctas. Tests en tests/test_stat_forwarding.py, con funciones extraídas por AST y dependencias simuladas, sin importar el programa completo ni abrir sockets/SQLite:

1. Retener el envío remoto de estadísticas en otro hilo y comprobar ACK local y reenvío de PULL_DATA/TX_ACK antes de liberar la respuesta.
2. Llenar 100 entradas; comprobar descarte/aviso, ACK local y continuidad del tráfico de control sin llamada remota desde receptor.
3. Procesar ACK válido, ausencia de ACK y excepción; verificar finalización de tarea de cola.
4. Paquete mixto rxpk+stat conserva save_packet antes del ACK y no entra a stat_queue.

CONFIRMADO por AST contra HEAD previo: local_receiver no contiene llamada a send_push_and_wait_ack, stat_worker registrado en main; funciones existentes salvo receptor/main sin cambios. No se prueban transporte real, temporización RX1/RX2 o entrega a TTN. PENDIENTE en una fase autorizada: comprobar en Raspberry tráfico de control durante silencio de TTN y saturación de estadísticas, latencia de SQLite y backlog. No se activa lorawan-queue.service ni se corta Internet en este prompt.


## PROMPT 005: validacion local del fast-path (2026-11-11)

CONFIRMADO: python -m py_compile lorawan_queue.py; python -B -m unittest discover -s tests -v: 12 pruebas correctas (8 nuevas, 4 existentes). SQLite temporal y sockets simulados, funciones cargadas por AST sin importar el proxy ni tocar DB de produccion. Cubren reserva/deduplicacion, ACK con token/tipo correcto, fallo/excepcion, reintento intacto con multiples rxpk, simulacion de reinicio, saturacion y paso de PULL_DATA/TX_ACK durante espera activa. La simulacion de reinicio no es un reinicio del servicio/sistema.

PENDIENTE: pruebas operacionales 1 online, 2 OTAA, 3 corte/restauracion y 4 reinicio del servicio/reboot pedidas por el usuario, despues de revision del diff y autorizacion de commit/push. Conservar los comandos de despliegue del prompt como sugeridos NO ejecutados. Medir RF, tmst, recepcion, envio, ACK, PULL_RESP y contador actual del concentrador; correlacionar TTN/aplicacion y TX_ACK, no deducir entrega de PUSH_ACK. La evidencia OTAA recibida del usuario no fue observada directamente; no cierra las fases 2/3 ni prueba causalidad del rechazo JIT. El intento SSH termino Permission denied antes de ejecutar comandos remotos.


### PROMPT 005: revision posterior de pruebas

CONFIRMADO: py_compile codigo 0 y 15 pruebas OK (1.402 s). La prueba de reintento se actualiza para comprobar reconstruccion de rxpk.time desde original_time, preservacion de cada tmst/cabecera/demas campos y raw_packet/metadata SQLite intactos. Tres pruebas adicionales verifican queue_worker omitiendo in_flight, fast_worker con parser real y ACK valido tras token/tipo incorrectos, y socket.timeout sin mark_sent. Transporte simulado y SQLite temporal: no equivalen a pruebas operacionales. Comparacion AST confirma fast_worker intacto frente al diff anterior y esquema/downstream/injector/ambas definiciones de tiempo intactos frente a HEAD. Saturacion preserva el uplink, no su ventana OTAA. Despliegue y medicion real PENDIENTES.


## PROMPT 006 — Dashboard SAMEE LoRaWAN Gateway (2026-11-15)

Implementación local autorizada expresamente; no cierra las fases operacionales anteriores, que permanecen PENDIENTES. No se modifica lorawan_queue.py ni la base existente.

Arquitectura: proceso FastAPI separado -> muestreador compartido (pausa 5 s después de cada muestra) -> API y WebSocket (2 s). SQLite URI mode=ro y query_only, timeout de bloqueo 20 ms, presupuesto VM 80 ms, últimos 100 registros. El agregado histórico puede agotar el presupuesto: estado UNKNOWN, sin índices ni migraciones nuevos. No se usa immutable porque la base cambia. Lecturas aún pueden competir por I/O/locks; medir impacto real PENDIENTE. No se crea gateway_events.

Archivos: dashboard/app.py, queue_monitor.py, system_monitor.py, gateway_monitor.py, device_decoder.py, templates/index.html y static locales; deploy/dashboard.service; requirements.txt y requirements-dev.txt; tests/test_dashboard.py.

API GET: /api/status, /api/system, /api/queue, /api/devices, /api/gateway, /api/services. WS /ws/status comparte caché, limita envío lento y rechaza origen web distinto al host. Cuatro vistas: resumen, dispositivos, cola con marcas disponibles y sistema. No sirve BLOB, token Semtech ni payload de aplicación. Usa textContent para datos externos.

Fuentes: CPU/RAM/disco/uptime/frecuencia/interfaces psutil; temperatura sysfs Linux; servicios systemctl show con timeout; Internet TCP a 1.1.1.1:443 y resolvectl query del host TTN (aproximación, no universal; sin resolvectl DNS UNKNOWN). TTN usa último ack_at: ONLINE hasta 120 s, luego DEGRADED; falta de ACK no demuestra OFFLINE. PUSH_ACK no acredita entrega final; PULL_ACK no disponible. RAK/SPI/GPS UNKNOWN; AU915 FSB1 solo declarado, no verificado. No se consultan logs crudos ni secretos. Sent/ACK comparten marca histórica; fast-send/commit exacto no registrados. Original_time puede ser fallback local, no siempre hora RF. No se estima autonomía sin historial.

Dispositivos: ventana de 100 datagramas, hasta 64 rxpk por datagrama; extracción local de DevAddr/DevEUI, FCnt16, FPort y metadatos RF. DevAddr no identifica permanentemente; no hay asociación verificada a LILYGO/Dragino/QALCOSONIC ni claves/decoder de aplicación local, por lo que valores son NO DISPONIBLES.

Ejecución local sugerida (NO ejecutada como servidor LAN): `python -m pip install -r requirements.txt`; configurar DASHBOARD_DB_PATH hacia base autorizada; `python -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8080 --workers 1`. Abrir http://127.0.0.1:8080. Sin base muestra UNKNOWN y no la crea. Dependencias dev: `python -m pip install -r requirements-dev.txt`. Tests: `python -m unittest discover -s tests -v`.

Raspberry PENDIENTE: después de revisión, aprobación de Jaime, commit/push PC y pull Raspberry; revisar puerto 8080 (antecedente de otro receptor), intérprete/usuario/rutas, acceso de lectura DB y journal, firewall LAN y systemd-analyze verify. Unidad preparada, NO instalada. Binding 0.0.0.0 sin autenticación requiere LAN confiable y firewall; no publicar en Internet. GPS/identidades y medición RF precisan fuentes validadas. Validar CPU/I/O, cola bajo backlog, online/offline/recuperación y WebSocket real en navegador. No probar corte ni reinicio ahora.


## PROMPT 007 — Revisión y puerta de despliegue

La ausencia de lorawan_queue.db en PC es comportamiento correcto. No copiar producción; pruebas SQLite exclusivamente temporales fuera del repositorio. Antes y después: `Get-ChildItem -Recurse -Force -File -Include *.db,*.db-journal,*.db-wal,*.db-shm`; `git ls-files | Select-String "\.db($|-wal$|-shm$|-journal$)"`; `git check-ignore -v lorawan_queue.db example.db-journal`. No deben aparecer datos operacionales ni auxiliares versionados/residuales.

Regresiones locales: fuentes Linux ausentes, systemctl incompleto, fallback DNS y timeout, ACK antiguo/futuro/sin evidencia, DB inexistente/bloqueada, JSON no objeto, lectura sin DML, límite 100 filas, read-lock liberado antes de decodificar y red retenida sin frenar cola. `python -m unittest discover -s tests -v`, `python -m py_compile dashboard/*.py tests/test_dashboard.py` (expandir archivos explícitamente en PowerShell), `node --check dashboard/static/js/dashboard.js`, `git diff --check`. Node/Playwright son herramientas de revisión PC, no requisitos del servicio.

Validación visual con Chrome headless: cuatro vistas en 1366x900 y 390x844, sin CDN ni solicitudes externas del navegador, estados ausentes explícitos, consola sin errores, tabla con scroll interno, reconexión WebSocket y servidor operativo tras cerrar navegador. Fixtures ficticias en TemporaryDirectory; capturas administrativas en .git, fuera del contenido versionado. Resultados reales en BITACORA PROMPT 007.

### Raspberry: comandos sugeridos NO ejecutados

Solo tras revisión y commit/push aprobados en PC:

```bash
cd /home/pi/lorawan_queue
git status
git pull --ff-only
sudo ss -ltnp | grep ':8080'
ls -lh /home/pi/lorawan_queue/lorawan_queue.db
sqlite3 -readonly /home/pi/lorawan_queue/lorawan_queue.db '.tables'
sqlite3 -readonly /home/pi/lorawan_queue/lorawan_queue.db 'SELECT status, COUNT(*) FROM uplink_queue GROUP BY status;'
stat /home/pi/lorawan_queue/lorawan_queue.db
systemd-analyze verify deploy/dashboard.service
```

Si `ss` ejecuta correctamente y no aparece listener 8080: disponible en ese momento; si aparece, NO instalar hasta identificar el proceso. No cambiar automáticamente el puerto ni detener otro receptor. Verificar versión Python >=3.10, dependencias en venv, usuario pi, rutas, permisos DB/auxiliares WAL, fuentes /proc y sysfs, firewall LAN. No abrir SQLite sin -readonly cuando se espera una DB existente: un nombre erróneo no debe crearla.

Después de comprobar lo anterior y autorizar instalación: instalar dashboard.service, daemon-reload, enable/start, status/journal y comparación de conteos con dashboard. Refrescar varias veces y comprobar que no se ejecuta DML. Con el productor activo los conteos y stat cambian legítimamente: comparar muestras correlacionadas y atribuir escrituras al proxy; igualdad de conteos/stat por sí sola no demuestra solo lectura. No detener la cola para esta prueba sin autorización. Medir carga/locks/latencia del fast-path y tráfico de control bajo backlog; después pruebas de pérdida Internet, recuperación y reboot con acceso local seguro. Todo permanece PENDIENTE en Raspberry.


## PROMPT 008 — Validación visual PYP

Validar cinco vistas en 1920x1080, 1366x768, tablet 900x1000, móvil 390x844 y 320x740: logo real visible sin deformación, tema claro, SVG locales, tablas con scroll interno y ausencia de scroll global. Menú móvil plegable, foco, Escape y cierre; fuentes ausentes y DB no disponible; selección de paquete y filtrado de eventos existentes. Ninguna cifra de demostración en producto.

Pruebas transitorias: fixture ficticia SQLite y control de red en TemporaryDirectory fuera del repositorio, Uvicorn loopback y navegador Chrome headless; las capturas fixture-* no acreditan operación Raspberry. Comprobar API HTTP 200, mensajes WS, transición OFFLINE/ONLINE con y sin pendientes, reconexión, DOM sin inyección HTML, hash DB de fixture sin cambios atribuibles al dashboard y hash del logo idéntico. Herramienta administrativa y evidencias locales en .git/dashboard-review-008, fuera de commits. Sin agregar dependencias frontend.

Ejecutar unittest, node --check y git diff --check; comprobar backend/proxy intactos y ausencia de .db/.db-journal/.db-wal/.db-shm residuales. Raspberry, navegación LAN real, hardware, servicios reales y carga de renderización en Raspberry permanecen PENDIENTES. El rediseño no cierra ninguna fase operacional anterior.


## PROMPT 009 - Validacion UPS

PENDIENTE hardware. PC: python -m unittest discover -s tests -v; node --check dashboard/static/js/dashboard.js; git diff --check. Tests SMBus simulado, sin /dev/i2c-1; signed 0xFFF8=-8, estados/celdas/delta, umbrales, ausente, error, incompleta, timeout y aislamiento de cache/API/WS. Pruebas PC no acreditan electricidad, firmware ni aislamiento RF.

Comandos Raspberry sugeridos NO ejecutados: despues de revision, commit/push PC y pull Raspberry, `sudo i2cdetect -y 1` (esperado 2d); comprobar import smbus en interprete de dashboard.service y permisos i2c; `curl -s http://127.0.0.1:8080/api/ups`; abrir http://192.168.5.169:8080. Contrastar con lectura original existente sin modificar ups.py. Comprobar valores reales, carga/descarga, alimentacion externa y celdas; no asumir umbrales oficiales. Observar muestreo/CPU/procesos hijos y recuperacion ante errores I2C seguros, sin desconexion electrica en caliente ni acciones de apagado.

Comando sugerido NO ejecutado: `systemctl is-active lorawan-queue.service ttn-gateway.service dashboard.service`. Correlacionar Pending, Sent, PUSH_ACK y latencia/control mientras UPS muestrea; servicio activo por si solo no prueba aislamiento. PUSH_ACK solo acredita recepcion UDP. Verificar API HTTP 200 y WS con UPS ausente o smbus inaccesible; UNKNOWN sin falsos ceros y recuperacion posterior. Revisar escritorio/movil (4 celdas/2x2), estados de bateria y muestra obsoleta. No ejecutar shutdown, poweroff, i2cset ni escribir registros. No efectuar estas pruebas remotas durante la implementacion PC.
