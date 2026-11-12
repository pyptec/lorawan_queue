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
