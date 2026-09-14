#!/usr/bin/env python3

import socket
import sqlite3
import hashlib
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# CONFIGURACION
# ============================================================

LOCAL_IP = "127.0.0.1"
LOCAL_PORT = 1700

TTN_HOST = "nam1.cloud.thethings.network"
TTN_PORT = 1700

DB_PATH = "/home/pi/lorawan_queue/lorawan_queue.db"

RETRY_INTERVAL = 5
SOCKET_TIMEOUT = 1.0


# ============================================================
# SEMTECH UDP
# ============================================================

PUSH_DATA = 0x00
PUSH_ACK  = 0x01
PULL_DATA = 0x02
PULL_RESP = 0x03
PULL_ACK  = 0x04
TX_ACK    = 0x05


# ============================================================
# VARIABLES
# ============================================================

last_push_client = None
last_pull_client = None

client_lock = threading.Lock()
db_lock = threading.Lock()

running = True


# ============================================================
# UTILIDADES
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def packet_type_name(packet_type):

    names = {
        PUSH_DATA: "PUSH_DATA",
        PUSH_ACK:  "PUSH_ACK",
        PULL_DATA: "PULL_DATA",
        PULL_RESP: "PULL_RESP",
        PULL_ACK:  "PULL_ACK",
        TX_ACK:    "TX_ACK",
    }

    return names.get(packet_type, f"UNKNOWN_{packet_type}")


def parse_semtech_packet(data):

    if len(data) < 4:
        return None

    version = data[0]
    token = data[1:3]
    packet_type = data[3]

    gateway_eui = None

    if packet_type in (PUSH_DATA, PULL_DATA, TX_ACK):

        if len(data) >= 12:
            gateway_eui = data[4:12].hex().upper()

    return {
        "version": version,
        "token": token,
        "type": packet_type,
        "gateway_eui": gateway_eui,
    }


# ============================================================
# BASE DE DATOS
# ============================================================

def init_db():

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS uplink_queue (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            received_at TEXT NOT NULL,

            gateway_eui TEXT,

            token TEXT,

            packet_hash TEXT NOT NULL UNIQUE,

            raw_packet BLOB NOT NULL,

            status TEXT NOT NULL DEFAULT 'pending',

            attempts INTEGER NOT NULL DEFAULT 0,

            last_attempt TEXT,

            sent_at TEXT,

            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_uplink_status
        ON uplink_queue(status, id)
    """)

    conn.commit()
    conn.close()


def save_packet(data, info):

    packet_hash = hashlib.sha256(data).hexdigest()

    now = utc_now()

    with db_lock:

        conn = sqlite3.connect(DB_PATH)

        try:

            conn.execute("""
                INSERT INTO uplink_queue (
                    received_at,
                    gateway_eui,
                    token,
                    packet_hash,
                    raw_packet,
                    status,
                    attempts,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', 0, ?)
            """, (
                now,
                info.get("gateway_eui"),
                info["token"].hex(),
                packet_hash,
                sqlite3.Binary(data),
                now
            ))

            conn.commit()

            packet_id = conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

            return packet_id, True

        except sqlite3.IntegrityError:

            return None, False

        finally:
            conn.close()


def get_pending_packets(limit=20):

    with db_lock:

        conn = sqlite3.connect(DB_PATH)

        rows = conn.execute("""
            SELECT
                id,
                raw_packet,
                attempts
            FROM uplink_queue
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT ?
        """, (limit,)).fetchall()

        conn.close()

    return rows


def mark_attempt(packet_id):

    with db_lock:

        conn = sqlite3.connect(DB_PATH)

        conn.execute("""
            UPDATE uplink_queue
            SET attempts = attempts + 1,
                last_attempt = ?
            WHERE id = ?
        """, (
            utc_now(),
            packet_id
        ))

        conn.commit()
        conn.close()


def mark_sent(packet_id):

    with db_lock:

        conn = sqlite3.connect(DB_PATH)

        conn.execute("""
            UPDATE uplink_queue
            SET status = 'sent',
                sent_at = ?
            WHERE id = ?
        """, (
            utc_now(),
            packet_id
        ))

        conn.commit()
        conn.close()


def get_statistics():

    with db_lock:

        conn = sqlite3.connect(DB_PATH)

        pending = conn.execute("""
            SELECT COUNT(*)
            FROM uplink_queue
            WHERE status='pending'
        """).fetchone()[0]

        sent = conn.execute("""
            SELECT COUNT(*)
            FROM uplink_queue
            WHERE status='sent'
        """).fetchone()[0]

        total = conn.execute("""
            SELECT COUNT(*)
            FROM uplink_queue
        """).fetchone()[0]

        conn.close()

    return total, pending, sent


# ============================================================
# ACK LOCAL PARA PUSH_DATA
# ============================================================

def build_push_ack(data):

    if len(data) < 4:
        return None

    version = data[0:1]
    token = data[1:3]

    return version + token + bytes([PUSH_ACK])


# ============================================================
# SOCKET LOCAL
# ============================================================

local_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

local_socket.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

local_socket.bind(
    (LOCAL_IP, LOCAL_PORT)
)


# ============================================================
# SOCKET HACIA TTN
# ============================================================

ttn_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

ttn_socket.settimeout(
    SOCKET_TIMEOUT
)


# ============================================================
# RECEPCION LOCAL
# ============================================================

def local_receiver():

    global last_push_client
    global last_pull_client

    print(
        f"[INFO] Escuchando packet forwarder en "
        f"{LOCAL_IP}:{LOCAL_PORT}"
    )

    while running:

        try:

            data, addr = local_socket.recvfrom(65535)

            info = parse_semtech_packet(data)

            if not info:
                continue

            packet_type = info["type"]

            # --------------------------------------------
            # PUSH_DATA
            # --------------------------------------------

            if packet_type == PUSH_DATA:

                with client_lock:
                    last_push_client = addr

                packet_id, inserted = save_packet(
                    data,
                    info
                )

                # ACK inmediato SOLO despues de guardar
                ack = build_push_ack(data)

                if ack:
                    local_socket.sendto(
                        ack,
                        addr
                    )

                if inserted:

                    print(
                        f"[RX] PUSH_DATA "
                        f"id={packet_id} "
                        f"GW={info['gateway_eui']} "
                        f"guardado"
                    )

                else:

                    print(
                        "[RX] PUSH_DATA duplicado"
                    )

            # --------------------------------------------
            # PULL_DATA
            # --------------------------------------------

            elif packet_type == PULL_DATA:

                with client_lock:
                    last_pull_client = addr

                try:

                    ttn_socket.sendto(
                        data,
                        (TTN_HOST, TTN_PORT)
                    )

                except Exception as e:

                    print(
                        f"[WARN] PULL_DATA TTN: {e}"
                    )

            # --------------------------------------------
            # TX_ACK
            # --------------------------------------------

            elif packet_type == TX_ACK:

                try:

                    ttn_socket.sendto(
                        data,
                        (TTN_HOST, TTN_PORT)
                    )

                except Exception as e:

                    print(
                        f"[WARN] TX_ACK TTN: {e}"
                    )

            else:

                print(
                    f"[LOCAL] "
                    f"{packet_type_name(packet_type)}"
                )

        except Exception as e:

            print(
                f"[ERROR] local_receiver: {e}"
            )

            time.sleep(1)


# ============================================================
# RECEPCION TTN
# ============================================================

def ttn_receiver():

    while running:

        try:

            data, remote = ttn_socket.recvfrom(
                65535
            )

            info = parse_semtech_packet(data)

            if not info:
                continue

            packet_type = info["type"]

            # --------------------------------------------
            # PULL_ACK
            # --------------------------------------------

            if packet_type == PULL_ACK:

                with client_lock:
                    target = last_pull_client

                if target:

                    local_socket.sendto(
                        data,
                        target
                    )

            # --------------------------------------------
            # PULL_RESP
            # --------------------------------------------

            elif packet_type == PULL_RESP:

                with client_lock:
                    target = last_pull_client

                if target:

                    local_socket.sendto(
                        data,
                        target
                    )

                    print(
                        "[DOWNLINK] PULL_RESP recibido"
                    )

            # PUSH_ACK remoto no se retransmite.
            # El packet forwarder ya recibio nuestro
            # PUSH_ACK local.

        except socket.timeout:
            pass

        except Exception as e:

            print(
                f"[ERROR] ttn_receiver: {e}"
            )

            time.sleep(1)


# ============================================================
# ENVIO DE COLA
# ============================================================

def queue_worker():

    print("[INFO] Worker de cola iniciado")

    while running:

        try:

            packets = get_pending_packets(
                limit=10
            )

            if not packets:

                time.sleep(RETRY_INTERVAL)
                continue

            for packet_id, raw_packet, attempts in packets:

                try:

                    mark_attempt(packet_id)

                    ttn_socket.sendto(
                        raw_packet,
                        (TTN_HOST, TTN_PORT)
                    )

                    # Primera version:
                    # marcamos como enviado tras sendto().
                    #
                    # En la siguiente etapa vincularemos
                    # PUSH_ACK remoto al token y solo entonces
                    # cambiaremos a SENT.

                    mark_sent(packet_id)

                    print(
                        f"[TX] id={packet_id} "
                        f"enviado a TTN"
                    )

                    time.sleep(0.05)

                except Exception as e:

                    print(
                        f"[QUEUE] TTN no disponible: {e}"
                    )

                    break

            time.sleep(1)

        except Exception as e:

            print(
                f"[ERROR] queue_worker: {e}"
            )

            time.sleep(RETRY_INTERVAL)


# ============================================================
# ESTADISTICAS
# ============================================================

def statistics_worker():

    while running:

        try:

            total, pending, sent = get_statistics()

            print(
                f"[QUEUE] total={total} "
                f"pending={pending} "
                f"sent={sent}"
            )

        except Exception as e:

            print(
                f"[ERROR] statistics: {e}"
            )

        time.sleep(60)


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("========================================")
    print(" SAMEE LoRaWAN Store & Forward")
    print("========================================")
    print(f"Gateway local : {LOCAL_IP}:{LOCAL_PORT}")
    print(f"TTN            : {TTN_HOST}:{TTN_PORT}")
    print(f"DB             : {DB_PATH}")
    print("")

    init_db()

    threads = [

        threading.Thread(
            target=local_receiver,
            daemon=True
        ),

        threading.Thread(
            target=ttn_receiver,
            daemon=True
        ),

        threading.Thread(
            target=queue_worker,
            daemon=True
        ),

        threading.Thread(
            target=statistics_worker,
            daemon=True
        ),
    ]

    for thread in threads:
        thread.start()

    try:

        while True:
            time.sleep(10)

    except KeyboardInterrupt:

        print("")
        print("[INFO] Deteniendo...")
        print("")


if __name__ == "__main__":
    main()