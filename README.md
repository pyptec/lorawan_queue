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
