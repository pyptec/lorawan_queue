# Bitácora del proyecto

## PROMPT 001

### ROL
Ingeniero IoT: LoRaWAN, Raspberry Pi, RAK5146/SX1303, TTN/TTS, Semtech UDP, Python, SQLite, FastAPI, Linux, Git, store-and-forward y visualización web.

### TAREA
Solicitud recibida: «PROMPT 001 — ESTRUCTURA DOCUMENTAL DEL PROYECTO LoRaWAN». Organizar, documentar y desarrollar progresivamente Raspberry Pi 4 + RAK5146 SPI + Semtech UDP Packet Forwarder + TTN + cola local + SQLite + dashboard. Mantener evidencia completa sin inventar resultados.

Registro de requisitos del prompt: instalación con repositorio oficial RAK; SPI; AU915 y bloque real de nodos; integración TTN; cola sin Internet; guardar uplinks y timestamp original; reintento automático; estados pending/sent/failed; no retardar downlinks; dashboard con estado gateway/TTN, pendientes/enviados/fallidos, último uplink/reenvío, intentos y timestamps original/envío; documentación reproducible y bitácora de prompts.

Regla de cola solicitada: conservar payload original, timestamp original, estado, intentos, último intento y fecha de envío. No almacenar ni retrasar downlinks, PULL_RESP, TX_ACK, Join Accept, RX1 o RX2.

Regla de modificación solicitada: revisar código, configuración y estado real; identificar problema; proponer cambio; cambiar únicamente en PC; commit; push; pull en Raspberry; validar; documentar.

Orden solicitado: documentación, gateway, TTN, auditoría de cola, sin Internet, reenvío, dashboard, servicios, recuperación/reinicio. No avanzar sin registrar resultado previo.

### FORMATO
Cada intervención: PROMPT XXX / ROL / TAREA / FORMATO / EVIDENCIA / ARCHIVOS CONSULTADOS / ARCHIVOS MODIFICADOS / COMANDOS EJECUTADOS / RESULTADO / VALIDACIÓN / PENDIENTES / ESTADO. Estados documentales: CONFIRMADO, PENDIENTE, HIPÓTESIS, ERROR, CORREGIDO. Esta entrada registra los requisitos del prompt; no es una transcripción literal completa.

### EVIDENCIA
Fecha: 2026-11-09, zona America/Bogota. PC Windows/PowerShell. Repositorio `D:\promate\raspberry\gateway-lora\scr`, rama main, HEAD inicial `a4a4cd64ae7096936fd02d897ac8e57ee5ad7e2e`. Git status inicial sin cambios. Origin: https://github.com/pyptec/lorawan_queue.git. Archivos rastreados iniciales: .gitignore, README.md, lorawan_queue.py. No se obtuvo evidencia de Raspberry, configuración activa, SQLite real, TTN o dispositivos.

Lectura estática: estados pending/sent; timestamp sustituido ante desfase >10 s; extractor duplicado; ACK local después de persistir; receptor espera ACK de estadísticas; PUSH_DATA genérico también encolado. Hallazgos en docs/ARQUITECTURA.md; sin cambios funcionales.

### ARCHIVOS CONSULTADOS
README.md, lorawan_queue.py, .gitignore; estado, remotos e historial Git. Búsqueda de AGENTS.md en antecesores y árbol D:\promate sin reglas aplicables encontradas. Fuentes web oficiales enumeradas en docs/FUENTES.md.

### ARCHIVOS MODIFICADOS
README.md actualizado. Creados: BITACORA.md, AGENTS.md, docs/README_PREVIO.md (copia del README original), docs/ARQUITECTURA.md, docs/PLAN_VALIDACION.md, docs/FUENTES.md. Ninguna modificación funcional prevista.

### COMANDOS EJECUTADOS
- `Get-Location`; `rg --files -g AGENTS.md -g README.md -g BITACORA.md -g '*.py' -g '*.json' -g '*.service' -g '*.md' -g '.gitignore'`.
- `git status --short`; `git remote -v`; `git log -5 --oneline`.
- `Get-Content README.md`; `Get-Content lorawan_queue.py`; `Get-Content .gitignore`; `git ls-files`.
- `Get-Item ..\AGENTS.md, ..\..\AGENTS.md, ..\..\..\AGENTS.md, D:\AGENTS.md -ErrorAction SilentlyContinue`: sin archivos; el comando compuesto devolvió 1 por rutas ausentes.
- `git branch --show-current`; `git rev-parse HEAD`.
- `rg -n 'def get_original_time|difference >|send_push_and_wait_ack|save_packet|time.sleep|status|bind|RETRY_INTERVAL' lorawan_queue.py`.
- `rg --files --hidden -g AGENTS.md -g '!\.git/**' D:\promate`: solo coincidencia ajena al proyecto.
- Consulta web de fuentes oficiales RAKWireless y The Things Stack mediante herramienta de búsqueda.
- Escritura documental PowerShell: New-Item docs, Copy-Item README.md a docs/README_PREVIO.md, Set-Content UTF-8 de los documentos listados. Requiere autorización de escritura por sandbox de solo lectura.

### RESULTADO
Estructura documental preparada para FASE 1. Arquitectura objetivo separada del comportamiento observado. Las afirmaciones del README anterior se conservan como antecedente sin validarlas. No se modificaron funciones ni se ejecutó el proxy.

### VALIDACIÓN
Inspección estática realizada. Validación de documentos, diff, commit y push pendientes de registrar tras la escritura. No se ejecutaron pruebas RF, corte de red, reenvío o downlink.

### PENDIENTES
Validar archivos; commit y push documental; registrar cierre de FASE 1; obtener acceso y evidencias de Raspberry para FASE 2. Pull y validación remota siguen PENDIENTES. No se conoce acceso SSH, EUI, revisión hardware, bloque AU915, configuración activa o servicio real.

### ESTADO
PENDIENTE: cierre de FASE 1 y verificaciones operativas. CONFIRMADO únicamente el inventario y los hallazgos estáticos indicados.

### Validación local posterior a la escritura
CONFIRMADO: presencia de los siete documentos, once secciones obligatorias y enlaces Markdown locales comprobados con PowerShell. `git diff --check` terminó con código 0. `git diff --quiet -- lorawan_queue.py .gitignore` devolvió 0: sin cambios funcionales. Git avisó de conversión futura LF a CRLF en README; no es un fallo funcional. No se ejecutó/importó el proxy. Comandos adicionales: git diff --stat; Test-Path y comprobaciones de secciones y enlaces con expresiones regulares. Commit y push se intentan después de esta anotación; su resultado no se presupone.

### Corrección de validación y publicación
ERROR observado: `git diff --cached --check` detectó una línea vacía final heredada en docs/README_PREVIO.md; se detuvo antes de commit/push. CORREGIDO: se normalizó únicamente el final de ese antecedente, conservando su contenido textual. Se repiten staging y validación antes de publicar. Comandos: git add de los siete documentos; git diff --cached --check; git commit; git push origin main; git status --short; git log -1 --oneline. Los resultados de publicación se registrarán después de observarlos.

### Cierre documental de FASE 1
CONFIRMADO: validación del staging con código 0; commit documental `a056dd7`; push a origin/main exitoso (`a4a4cd6..a056dd7`); git status --short sin cambios tras publicar. Solo siete archivos documentales modificados/creados. Se registra el resultado antes de abrir otra fase. FASE 1 CONFIRMADO en su alcance documental; no confirma operación del sistema. FASE 2 PENDIENTE por falta de acceso y evidencia del gateway. Pull en Raspberry y validación remota PENDIENTES. Esta anotación de cierre se publica mediante un commit documental adicional.

## PROMPT 002

### ROL
Ingeniero IoT/Linux; auditoría solo lectura.
### TAREA
Auditar repositorio, archivos, procesos, systemd, UDP, SQLite, estados, tiempos, reintentos y logs sin editar ni ejecutar Git de escritura.
### FORMATO
Doce apartados de auditoría y estados permitidos; registro retrospectivo autorizado documentalmente en PROMPT 003.
### EVIDENCIA
Lectura del adjunto Pasted text.txt, reglas y configuración SSH local. Alias rak-gateway: pi@192.168.2.129. Dos intentos rechazados con Permission denied (publickey,password); el segundo tras el aviso del usuario de que había cerrado otra aplicación. Ningún comando remoto llegó a ejecutarse.
### ARCHIVOS CONSULTADOS
Adjunto PROMPT 002, AGENTS.md, configuración SSH del PC y documentación local.
### ARCHIVOS MODIFICADOS
Ninguno durante PROMPT 002. Esta entrada se añade durante PROMPT 003.
### COMANDOS EJECUTADOS
Get-Content; git status --short; git log -3 --oneline; Get-Command ssh; búsqueda local rg. Dos intentos: ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o ConnectTimeout=10 rak-gateway con consultas hostname/uname/date/estado Git; ambos terminaron con código 1 antes de ejecutar consultas remotas.
### RESULTADO
Auditoría remota PENDIENTE. En PROMPT 003 el usuario aporta como resultado de PROMPT 002: Packet Forwarder directo a TTN, cola no activa, 58 eventos históricos sent, proxy sin escucha y Uvicorn :8080 ejecutando ttn_iotrack_receiver.py.
### VALIDACIÓN
CONFIRMADO el rechazo SSH observado y la recepción de información del usuario. Sin salidas remotas brutas para corroborar esos resultados directamente.
### PENDIENTES
Contrastar configuración, versión desplegada, procesos, unidad, DB y actividad con evidencia remota.
### ESTADO
PENDIENTE para auditoría directa; ERROR de autenticación observado. No inferir operación actual de 58 sent históricos.

## PROMPT 003

### ROL
Ingeniero IoT/Linux, LoRaWAN/RAK5146/Semtech UDP/Python/SQLite/systemd; trabajo exclusivamente en PC.
### TAREA
Preparar activación controlada: revisar código completo y documentos, crear deploy/lorawan-queue.service con Python .venv y usuario pi, documentar cambio manual del forwarder a localhost, validar sintaxis y preparar commit/push. No instalar ni cambiar Raspberry; no introducir cambios funcionales innecesarios.
### FORMATO
Secciones permanentes y estados permitidos. Resumen fiel de requisitos, no transcripción literal del prompt.
### EVIDENCIA
HEAD inicial c938de39fb36ee2c8b4d1d39943da11178a789bb, main, árbol limpio. Python del PC: Python310/python.exe. Lectura completa de lorawan_queue.py, README.md, AGENTS.md y BITACORA.md; lectura de arquitectura y plan. Estado remoto provisto por el usuario con procedencia indicada en PROMPT 002.
### ARCHIVOS CONSULTADOS
lorawan_queue.py, README.md, AGENTS.md, BITACORA.md, docs/ARQUITECTURA.md, docs/PLAN_VALIDACION.md; Git y resolución de Python.
### ARCHIVOS MODIFICADOS
deploy/lorawan-queue.service (nuevo); README.md, BITACORA.md, docs/ARQUITECTURA.md y docs/PLAN_VALIDACION.md. Código Python sin cambios.
### COMANDOS EJECUTADOS
Get-Content completo de los archivos indicados; lectura adicional del tramo final del Python y README ante truncamiento de salida; git status --short; git rev-parse HEAD; git remote -v; Get-Command python,py. New-Item deploy; Set-Content ASCII para unidad y Add-Content UTF-8 para documentación. Comandos de validación y publicación se registran tras observar resultados.
### RESULTADO
Preparado servicio User=pi, WorkingDirectory=/home/pi/lorawan_queue, ExecStart con .venv/bin/python3 y script absoluto, Restart=always, RestartSec=5. Salida Python sin buffer para journal. Documentados instalación futura, revisión, cambio manual JSON, validación y reversión sin ejecutar nada remoto.
### VALIDACIÓN
Flujo uplink y ramas directas confirmados por inspección estática. No puede confirmarse ausencia de retardos indirectos: receptor compartido con SQLite/espera de estadísticas y worker con intervalo ocioso/backlog. Se conserva el código y se documenta limitación antes de activar. Sintaxis, unidad y Git pendientes de comprobación posterior a escritura.
### PENDIENTES
Validar sintaxis y unidad local; commit/push PC. Validación nativa systemd, rutas/permisos en Raspberry y pruebas RF/TTN siguen PENDIENTES. Resolver/verificar requisito temporal antes de activar.
### ESTADO
PENDIENTE validación local y publicación. Preparación únicamente; sin activación real.

### Validación local de PROMPT 003
CONFIRMADO: `python -m py_compile lorawan_queue.py` terminó con código 0 sin salida de error; no se importó ni ejecutó el módulo. `git diff --check` código 0. `git diff --quiet -- lorawan_queue.py` código 0: Python intacto. Comprobaciones PowerShell de cinco directivas requeridas de unidad y enlaces locales: OK. Servicio guardado con saltos LF. Instrucción futura de venv condicionada a directorio ausente. Rutas Linux revisadas como valores declarados; existencia/permisos remotos PENDIENTES. systemd-analyze no ejecutado en Windows; validación nativa PENDIENTE. No hubo conexión SSH ni cambios en Raspberry durante este prompt.

Resultado de preparación local: CONFIRMADO. Arquitectura directa por ramas CONFIRMADO por código; ausencia de latencia y activación real PENDIENTES. A continuación se ejecutan desde PC: git add explícito de cinco archivos, git diff --cached --check, git commit y git push origin main; sus resultados se informan tras observarlos. No se modifica AGENTS.md ni archivos históricos.

## PROMPT 004

### ROL
Ingeniero IoT/Linux: LoRaWAN, Semtech UDP, RAK5146/SX1303, Python multihilo, UDP, SQLite y TTN; trabajo solo en PC.

### TAREA
Prompt recibido en adjunto Pasted text.txt: eliminar espera remota de estadísticas en local_receiver con cola thread-safe acotada y stat_worker independiente; ACK local primero; descartar sin bloqueo si llena con aviso específico. Preservar uplinks SQLite y rutas downlink, compilar, documentar, commit y push. No activar servicio ni modificar Raspberry. Este registro resume el prompt recibido.

### FORMATO
Secciones permanentes; estados permitidos y entrega de archivos, resumen, py_compile, commit y push.

### EVIDENCIA
HEAD inicial 831a030, árbol limpio. Código local revisado completamente y constantes coincidentes con contexto aportado. Rama has_stat llamaba send_push_and_wait_ack: espera ACK_TIMEOUT=2.0 s y potencial espera adicional por push_lock. Estado remoto histórico aportado por el usuario se conserva con su procedencia; no se realizó conexión remota durante este prompt.

### ARCHIVOS CONSULTADOS
Adjunto PROMPT 004, AGENTS.md, lorawan_queue.py, README.md, docs/ARQUITECTURA.md, docs/PLAN_VALIDACION.md y tramo de BITACORA.md de intervenciones anteriores; Git HEAD/estado.

### ARCHIVOS MODIFICADOS
lorawan_queue.py; tests/test_stat_forwarding.py (nuevo); README.md; BITACORA.md; docs/ARQUITECTURA.md; docs/PLAN_VALIDACION.md. Unidad systemd sin cambios.

### COMANDOS EJECUTADOS
Get-Content de adjunto/reglas/código/documentos; git status --short; git log -1 --oneline. Escritura local mediante PowerShell con comprobación de bloques esperados y UTF-8 sin BOM; creación tests. python -m py_compile lorawan_queue.py; python -m unittest discover -s tests -v; git diff --check; git diff -- lorawan_queue.py. Script Python leído desde stdin compara AST actual con git show HEAD:lorawan_queue.py y verifica ausencia de espera ACK en receptor y registro del worker. Actualización documental mediante PowerShell. Validación final y Git de publicación se ejecutan después de esta anotación.

### RESULTADO
CORREGIDO el bloqueo por ACK/lock remoto de estadísticas en el receptor: import queue, stat_queue maxsize=100, ACK local seguido de put_nowait con captura queue.Full y aviso requerido. stat_worker consume con timeout, usa envío/ACK existente y task_done en finally; daemon añadido en main. Estadísticas volátiles descartables, sin reintento propio; up_socket/push_lock conservados para serializar ACK con worker de uplinks. Se mantiene íntegra la lógica rxpk, SQLite, queue_worker, timestamps, estados y downstream.

### VALIDACIÓN
CONFIRMADO: py_compile código 0; cuatro pruebas correctas (0.028 s): receptor continúa con ACK remoto retenido, cola llena no bloquea tráfico de control, finalización de tarea en ACK/no ACK/error, prioridad de rxpk sobre stat en paquetes mixtos. Comparación AST confirma que solo local_receiver y main cambian entre funciones existentes y se añade stat_worker. Validación aislada sin UDP/TTN/SQLite real; no acredita latencia real ni ausencia total de bloqueos. git diff --check código 0 antes de actualizar documentos; se repite antes de commit.

### PENDIENTES
Commit/push tras validar documentación; pull y pruebas remotas futuras solo en intervención autorizada. Persistencia SQLite, idle/backlog y temporización LoRaWAN siguen pendientes, fuera del objetivo. No activar servicio todavía.

### ESTADO
CORREGIDO y CONFIRMADO en PC para la espera remota de estadísticas del receptor. PENDIENTE validación operacional. Sin cambios en Raspberry.
