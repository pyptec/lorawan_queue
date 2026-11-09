# lorawan_queue

**Store & Forward** para gateways LoRaWAN que hablan el protocolo Semtech UDP (como el
**RAK5146**) hacia **The Things Network (TTN)**, con cola persistente en SQLite para no
perder paquetes cuando la conexión a internet del gateway falla o es intermitente.

Corre como proxy local: el gateway apunta su *packet forwarder* a `127.0.0.1:1700` (este
script) en vez de apuntar directo a TTN. El script reenvía todo a TTN y, si algo falla,
encola el paquete y reintenta más tarde — sin que el gateway se entere ni tenga que
reintentar nada por su cuenta.

## Contexto de uso

Pensado para un **RAK5146 conectado a una Raspberry Pi 4** (`DB_PATH` apunta por defecto
a `/home/pi/lorawan_queue/lorawan_queue.db`), registrado como *gateway* en **The Things
Stack Sandbox**, recibiendo uplinks de dispositivos LoRaWAN (p. ej. un medidor de agua
QALCOSONIC W1, sensores Dragino LHT65N, nodos LILYGO) y reenviándolos a TTN para que de
ahí lleguen a la plataforma final vía integración/webhook.

## El problema que resuelve

Un *packet forwarder* Semtech UDP estándar (el que trae cualquier gateway LoRaWAN de
fábrica) **no guarda nada**: si en el instante en que llega un uplink no hay conexión a
internet, ese paquete se pierde para siempre — no hay reintento, no hay cola. Para un
gateway en un sitio con conectividad poco confiable, eso significa lecturas perdidas sin
ninguna evidencia de que ocurrieron.

`lorawan_queue.py` se interpone entre el gateway y TTN: **ack-ea al gateway de inmediato**
(para que nunca vea un fallo ni reintente por su cuenta) y guarda cada uplink real en
SQLite antes de intentar reenviarlo. Si TTN no responde, el paquete queda `pending` y se
reintenta automáticamente — sin perder el dato ni bloquear la recepción de los
siguientes uplinks.

## Arquitectura

```
                    UDP :1700                          UDP :1700
 [Gateway RAK5146] <===========> [lorawan_queue.py] <===========> [TTN]
  (packet forwarder                  (este script,                nam1.cloud.
   Semtech UDP,                      en 127.0.0.1:1700)            thethings.network
   apunta aquí)                            |
                                            v
                                   SQLite: uplink_queue
                                   (cola persistente,
                                    status pending/sent)
```

**Hilos del script** (`threading`, todos daemon):

| Hilo | Qué hace |
|---|---|
| `local_receiver` | Escucha al gateway en `127.0.0.1:1700`. Separa uplinks reales (`rxpk`), estadísticas (`stat`), `PULL_DATA` y `TX_ACK`. |
| `downstream_receiver` | Escucha respuestas de TTN (`PULL_ACK`, `PULL_RESP`) y las reenvía al gateway. |
| `queue_worker` | Toma paquetes `pending` de la base de datos, en lotes, y los reenvía a TTN esperando `PUSH_ACK` real. |
| `statistics_worker` | Imprime en consola un resumen (total / pending / sent) cada vez que cambia el estado. |

## Protocolo Semtech UDP: qué hace con cada tipo de paquete

| Tipo | Origen → Destino | Comportamiento |
|---|---|---|
| `PUSH_DATA` con `rxpk` (uplink real) | Gateway → script | ACK local inmediato al gateway + se guarda en la cola SQLite (no se reenvía de inmediato; lo hace `queue_worker`) |
| `PUSH_DATA` con `stat` (estadísticas del gateway) | Gateway → script | ACK local inmediato + reenvío **directo y síncrono** a TTN (no se encola) |
| `PULL_DATA` (el gateway pregunta por downlinks) | Gateway → script → TTN | Se reenvía de inmediato a TTN; se recuerda la dirección del gateway para rutear la respuesta |
| `PULL_ACK` / `PULL_RESP` (downlink) | TTN → script → Gateway | Se reenvía de inmediato al último gateway que hizo `PULL_DATA` |
| `TX_ACK` (confirmación de transmisión del gateway) | Gateway → script → TTN | Se reenvía de inmediato a TTN |

Solo los **uplinks reales (`rxpk`)** pasan por la cola persistente; todo lo demás
(estadísticas, keepalive de downlinks) se reenvía en vivo porque no tiene sentido
guardarlo para después.

## Deduplicación y preservación del tiempo original

- Cada paquete se identifica por el **hash SHA-256** de sus bytes crudos (columna
  `packet_hash`, `UNIQUE` en la base de datos). Si el gateway reenvía el mismo uplink
  (p. ej. porque no recibió el ACK a tiempo), el duplicado se descarta silenciosamente.
- Al recibir un uplink, se extrae `rxpk[0].time` (el timestamp que reporta el propio
  gateway) y se guarda como `original_time`. Si ese tiempo difiere más de **10 segundos**
  del reloj local, se descarta por no confiable y se usa la hora local UTC en su lugar
  (cubre el caso de un RAK5146 sin GPS/NTP estable).
- Cuando el `queue_worker` finalmente reenvía un paquete —segundos o hasta 60s+ después,
  si hubo que reintentar— **reescribe `rxpk[].time` con el `original_time` guardado**,
  no con la hora del reenvío. Así TTN recibe siempre el instante real en que ocurrió el
  uplink, aunque el envío efectivo haya sido tardío.

## Esquema de la base de datos (`uplink_queue`)

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Autoincremental |
| `received_at` | TEXT | Cuándo lo recibió este script (ISO, hora de recepción local) |
| `original_time` | INTEGER | Epoch Unix del uplink real, según `rxpk.time` o reloj local |
| `gateway_eui` | TEXT | EUI del gateway que lo envió |
| `token` | TEXT | Token Semtech del paquete (hex) |
| `packet_hash` | TEXT UNIQUE | SHA-256 del paquete crudo (deduplicación) |
| `raw_packet` | BLOB | Paquete Semtech UDP completo, tal cual llegó |
| `status` | TEXT | `pending` o `sent` |
| `attempts` | INTEGER | Veces que se intentó reenviar |
| `last_attempt` / `sent_at` / `ack_at` | TEXT | Marcas de tiempo del ciclo de reenvío |
| `delay_seconds` | INTEGER | `sent_at − original_time`: cuánto tardó en salir desde que ocurrió de verdad |

## Configuración

Todo está como constantes al inicio de `lorawan_queue.py` (no hay archivo de config
externo todavía):

```python
LOCAL_IP = "127.0.0.1"
LOCAL_PORT = 1700                               # donde debe apuntar el packet forwarder del gateway

TTN_HOST = "nam1.cloud.thethings.network"       # región de TTN (cambiar según tu Network Server)
TTN_PORT = 1700

DB_PATH = "/home/pi/lorawan_queue/lorawan_queue.db"   # pensado para correr en una Raspberry Pi

ACK_TIMEOUT = 2.0        # segundos de espera por PUSH_ACK antes de considerar fallido un envío
RETRY_INTERVAL = 60      # pausa tras un fallo de envío antes de reintentar el lote
QUEUE_BATCH_SIZE = 10    # paquetes pending que se intentan reenviar por ciclo
IDLE_INTERVAL = 5        # pausa cuando no hay nada pending
```

**Nota de comportamiento del `queue_worker`:** procesa el lote en orden; si **un**
paquete falla (sin `PUSH_ACK` dentro de `ACK_TIMEOUT`), se detiene el lote completo en
ese punto (no sigue con los siguientes del lote) y espera `RETRY_INTERVAL` antes de
volver a intentar desde el más antiguo `pending`. Es una estrategia simple en orden
estricto (FIFO), consciente de que un paquete atascado retrasa a los que le siguen.

## Cómo correrlo

```bash
python3 lorawan_queue.py
```

Configura el *packet forwarder* del gateway (RAK5146 u otro compatible con Semtech UDP)
para que apunte a `127.0.0.1:1700` en vez de a TTN directamente — este script hace el
reenvío real hacia `TTN_HOST`/`TTN_PORT`.

Para dejarlo corriendo de forma permanente en la Raspberry Pi, como servicio systemd:

```ini
[Unit]
Description=LoRaWAN Store & Forward Queue (RAK5146 -> TTN)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pi/lorawan_queue
ExecStart=/usr/bin/python3 /home/pi/lorawan_queue/lorawan_queue.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Salida en consola

El `statistics_worker` imprime un resumen cada vez que el estado cambia:

```
==============================================
 SAMEE LoRaWAN Queue Status
==============================================
 Total     : 42
 Pending   : 1
 Sent      : 41
 Last      : id=42 time=1793959200 status=pending attempts=0 delay=None
 Oldest    : id=42 time=1793959200
==============================================
```

Más los eventos en vivo por cada paquete (`[RX]`, `[TX]`, `[ACK]`, `[NO ACK]`,
`[DOWNLINK]`).

## Requisitos

Solo librería estándar de Python 3 (`socket`, `sqlite3`, `threading`, `json`,
`hashlib`, `datetime`) — no hay dependencias externas que instalar.
