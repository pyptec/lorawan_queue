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
