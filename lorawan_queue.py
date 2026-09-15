#!/usr/bin/env python3

import socket
import sqlite3
import hashlib
import threading
import time
import json
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

ACK_TIMEOUT = 2.0
RETRY_INTERVAL = 5
QUEUE_BATCH_SIZE = 10


# ============================================================
# SEMTECH UDP
# ============================================================

PUSH_DATA = 0x00
PUSH_ACK = 0x01
PULL_DATA = 0x02
PULL_RESP = 0x03
PULL_ACK = 0x04
TX_ACK = 0x05


# ============================================================
# VARIABLES
# ============================================================

running = True

last_pull_client = None

client_lock = threading.Lock()
db_lock = threading.Lock()
push_lock = threading.Lock()


# ============================================================
# UTILIDADES
# ============================================================
def utc_epoch():
    """
    Hora actual UTC en Unix Epoch, segundos.
    Ejemplo: 1726167992
    """
    return int(time.time())


def epoch_to_iso_z(epoch_value):
    """
    Convierte Unix Epoch UTC a ISO-8601 UTC para metadata Semtech.
    Ejemplo:
    1726167992 -> 2024-09-12T15:06:32.000Z
    """
    return (
        datetime.fromtimestamp(
            epoch_value,
            tz=timezone.utc
        )
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def packet_type_name(packet_type):
    names = {
        PUSH_DATA: "PUSH_DATA",
        PUSH_ACK: "PUSH_ACK",
        PULL_DATA: "PULL_DATA",
        PULL_RESP: "PULL_RESP",
        PULL_ACK: "PULL_ACK",
        TX_ACK: "TX_ACK",
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


def parse_push_json(data):
    if len(data) <= 12:
        return {}

    try:
        payload = data[12:].decode("utf-8")
        return json.loads(payload)

    except Exception:
        return {}


def contains_rxpk(data):
    obj = parse_push_json(data)

    rxpk = obj.get("rxpk")

    return isinstance(rxpk, list) and len(rxpk) > 0


def contains_stat(data):
    obj = parse_push_json(data)

    return "stat" in obj


# ============================================================
# BASE DE DATOS
# ============================================================

def init_db():
    Path(DB_PATH).parent.mkdir(
        parents=True,
        exist_ok=True
    )

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
            ack_at TEXT,
            created_at TEXT NOT NULL
        )
    """)

    columns = [
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(uplink_queue)"
        ).fetchall()
    ]
    
    if "original_time" not in columns:
        conn.execute(
            "ALTER TABLE uplink_queue "
            "ADD COLUMN original_time INTEGER"
        )

    if "delay_seconds" not in columns:
        conn.execute(
            "ALTER TABLE uplink_queue "
            "ADD COLUMN delay_seconds INTEGER"
        )

    if "ack_at" not in columns:
        conn.execute(
            "ALTER TABLE uplink_queue ADD COLUMN ack_at TEXT"
        )

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_uplink_status
        ON uplink_queue(status, id)
    """)

    conn.commit()
    conn.close()


def save_packet(data, info):

    packet_hash = hashlib.sha256(data).hexdigest()

    received_at = utc_now()

    # Hora REAL/original del paquete
    # Unix Epoch UTC
    original_time = utc_epoch()

    with db_lock:

        conn = sqlite3.connect(DB_PATH)

        try:

            cursor = conn.execute("""
                INSERT INTO uplink_queue (
                    received_at,
                    original_time,
                    gateway_eui,
                    token,
                    packet_hash,
                    raw_packet,
                    status,
                    attempts,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?)
            """, (
                received_at,
                original_time,
                info.get("gateway_eui"),
                info["token"].hex().upper(),
                packet_hash,
                sqlite3.Binary(data),
                received_at
            ))

            conn.commit()

            return (
                cursor.lastrowid,
                True,
                original_time
            )

        except sqlite3.IntegrityError:

            return None, False, None

        finally:

            conn.close()


def get_pending_packets(limit=10):

    with db_lock:

        conn = sqlite3.connect(DB_PATH)

        rows = conn.execute("""
            SELECT
                id,
                raw_packet,
                attempts,
                received_at,
                original_time
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

    now_iso = utc_now()
    now_epoch = utc_epoch()

    with db_lock:

        conn = sqlite3.connect(DB_PATH)

        row = conn.execute("""
            SELECT original_time
            FROM uplink_queue
            WHERE id = ?
        """, (
            packet_id,
        )).fetchone()

        delay_seconds = None

        if row and row[0] is not None:

            delay_seconds = (
                now_epoch - int(row[0])
            )

        conn.execute("""
            UPDATE uplink_queue
            SET status = 'sent',
                sent_at = ?,
                ack_at = ?,
                delay_seconds = ?
            WHERE id = ?
        """, (
            now_iso,
            now_iso,
            delay_seconds,
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

def inject_original_time(data, original_time):

    if len(data) <= 12:
        return data

    try:

        header = data[:12]

        payload = json.loads(
            data[12:].decode("utf-8")
        )

        rxpk = payload.get("rxpk")

        if not isinstance(rxpk, list):
            return data

        # Semtech rxpk.time requiere ISO UTC,
        # aunque nosotros internamente guardemos Epoch.
        original_time_iso = epoch_to_iso_z(
            original_time
        )

        for packet in rxpk:

            if isinstance(packet, dict):

                packet["time"] = original_time_iso

        new_payload = json.dumps(
            payload,
            separators=(",", ":")
        ).encode("utf-8")

        return header + new_payload

    except Exception as e:

        print(
            f"[WARN] No se pudo agregar "
            f"original_time: {e}"
        )

        return data
# ============================================================
# ACK LOCAL
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
# SOCKET DOWNSTREAM TTN
# ============================================================

down_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

down_socket.settimeout(1.0)


# ============================================================
# SOCKET UPSTREAM / COLA
# ============================================================

up_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

up_socket.settimeout(
    ACK_TIMEOUT
)


# ============================================================
# ENVIO PUSH CON ACK REAL TTN
# ============================================================

def send_push_and_wait_ack(data):
    info = parse_semtech_packet(data)

    if not info:
        return False

    expected_token = info["token"]

    with push_lock:
        try:
            up_socket.sendto(
                data,
                (TTN_HOST, TTN_PORT)
            )

            deadline = time.time() + ACK_TIMEOUT

            while time.time() < deadline:
                try:
                    response, remote = up_socket.recvfrom(
                        65535
                    )

                except socket.timeout:
                    return False

                response_info = parse_semtech_packet(
                    response
                )

                if not response_info:
                    continue

                if (
                    response_info["type"] == PUSH_ACK
                    and
                    response_info["token"] == expected_token
                ):
                    return True

            return False

        except Exception as e:
            print(
                f"[WARN] Error enviando PUSH_DATA: {e}"
            )
            return False

# ============================================================
# RECEPCION LOCAL
# ============================================================

def local_receiver():
    global last_pull_client

    print(
        f"[INFO] Escuchando packet forwarder en "
        f"{LOCAL_IP}:{LOCAL_PORT}"
    )

    while running:
        try:
            data, addr = local_socket.recvfrom(
                65535
            )

            info = parse_semtech_packet(data)

            if not info:
                continue

            packet_type = info["type"]

            # ==================================================
            # PUSH_DATA
            # ==================================================

            if packet_type == PUSH_DATA:

                has_rxpk = contains_rxpk(data)
                has_stat = contains_stat(data)

                # UPLINK RF REAL
                if has_rxpk:

                    packet_id, inserted, original_time = save_packet(
                        data,
                        info
                    )

                    ack = build_push_ack(data)

                    if ack:
                        local_socket.sendto(
                            ack,
                            addr
                        )

                    if inserted:
                        print(
                            f"[RX] id={packet_id} "
                            f"GW={info['gateway_eui']} "
                            f"original_time={original_time} "
                            f"-> PENDING"
                        )

                    else:
                        print(
                            f"[RX] duplicado "
                            f"token={info['token'].hex().upper()}"
                        )

                # SOLO ESTADISTICAS
                elif has_stat:

                    ack = build_push_ack(data)

                    if ack:
                        local_socket.sendto(
                            ack,
                            addr
                        )

                    ok = send_push_and_wait_ack(data)

                    if ok:
                        print(
                            "[STAT] enviado a TTN"
                        )

                    else:
                        print(
                            "[STAT] TTN sin respuesta"
                        )

                # PUSH_DATA NO IDENTIFICADO
                else:

                    packet_id, inserted, original_time = save_packet(
                        data,
                        info
                    )

                    ack = build_push_ack(data)

                    if ack:
                        local_socket.sendto(
                            ack,
                            addr
                        )

                    print(
                        f"[RX] PUSH_DATA genérico "
                        f"id={packet_id}"
                    )

            # ==================================================
            # PULL_DATA
            # ==================================================

            elif packet_type == PULL_DATA:

                with client_lock:
                    last_pull_client = addr

                try:
                    down_socket.sendto(
                        data,
                        (TTN_HOST, TTN_PORT)
                    )

                except Exception as e:
                    print(
                        f"[WARN] PULL_DATA: {e}"
                    )

            # ==================================================
            # TX_ACK
            # ==================================================

            elif packet_type == TX_ACK:

                try:
                    down_socket.sendto(
                        data,
                        (TTN_HOST, TTN_PORT)
                    )

                except Exception as e:
                    print(
                        f"[WARN] TX_ACK: {e}"
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
# RECEPCION DOWNSTREAM TTN
# ============================================================

def downstream_receiver():

    while running:
        try:
            data, remote = down_socket.recvfrom(
                65535
            )

            info = parse_semtech_packet(data)

            if not info:
                continue

            packet_type = info["type"]

            if packet_type == PULL_ACK:

                with client_lock:
                    target = last_pull_client

                if target:
                    local_socket.sendto(
                        data,
                        target
                    )

            elif packet_type == PULL_RESP:

                with client_lock:
                    target = last_pull_client

                if target:
                    local_socket.sendto(
                        data,
                        target
                    )

                    print(
                        "[DOWNLINK] PULL_RESP TTN -> RAK"
                    )

        except socket.timeout:
            pass

        except Exception as e:
            print(
                f"[ERROR] downstream_receiver: {e}"
            )

            time.sleep(1)


# ============================================================
# WORKER COLA
# ============================================================

def queue_worker():

    print(
        "[INFO] Worker de cola iniciado"
    )

    while running:
        try:
            packets = get_pending_packets(
                limit=QUEUE_BATCH_SIZE
            )

            if not packets:
                time.sleep(RETRY_INTERVAL)
                continue

            for (
                packet_id,
                raw_packet,
                attempts,
                received_at,
                original_time
            ) in packets:

                mark_attempt(packet_id)

                print(
                    f"[TX] id={packet_id} "
                    f"time_original={original_time} "
                    f"intento={attempts + 1} -> TTN"
                )

               
                ack_ok = send_push_and_wait_ack(
                    packet_to_send
                )
                
                packet_to_send = inject_original_time(
                    raw_packet,
                    original_time
                )

                if ack_ok:
                    mark_sent(packet_id)

                    delay = utc_epoch() - int(original_time)

                    print(
                        f"[ACK] id={packet_id} -> SENT "
                        f"| original_time={original_time} "
                        f"| delay={delay}s"
                    )

                else:
                    print(
                        f"[NO ACK] id={packet_id} "
                        f"permanece PENDING "
                        f"| original_time={original_time}"
                    )

                    break

                time.sleep(0.10)

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

    last_state = None

    while running:

        try:

            total, pending, sent = get_statistics()

            with db_lock:

                conn = sqlite3.connect(DB_PATH)

                last_row = conn.execute("""
                    SELECT
                        id,
                        original_time,
                        status,
                        attempts,
                        delay_seconds
                    FROM uplink_queue
                    ORDER BY id DESC
                    LIMIT 1
                """).fetchone()

                oldest_pending = conn.execute("""
                    SELECT
                        id,
                        original_time
                    FROM uplink_queue
                    WHERE status='pending'
                    ORDER BY id ASC
                    LIMIT 1
                """).fetchone()

                conn.close()

            state = (
                total,
                pending,
                sent,
                last_row,
                oldest_pending
            )

            # Solo imprime si algo cambia
            if state != last_state:

                print("")
                print("==============================================")
                print(" SAMEE LoRaWAN Queue Status")
                print("==============================================")
                print(f" Total     : {total}")
                print(f" Pending   : {pending}")
                print(f" Sent      : {sent}")

                if last_row:

                    print(
                        f" Last      : id={last_row[0]} "
                        f"time={last_row[1]} "
                        f"status={last_row[2]} "
                        f"attempts={last_row[3]} "
                        f"delay={last_row[4]}"
                    )

                if oldest_pending:

                    print(
                        f" Oldest    : id={oldest_pending[0]} "
                        f"time={oldest_pending[1]}"
                    )

                print("==============================================")
                print("")

                last_state = state

        except Exception as e:

            print(
                f"[ERROR] statistics_worker: {e}"
            )

        time.sleep(5)

# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("========================================")
    print(" SAMEE LoRaWAN Store & Forward V2")
    print("========================================")
    print(
        f"Gateway local : "
        f"{LOCAL_IP}:{LOCAL_PORT}"
    )
    print(
        f"TTN           : "
        f"{TTN_HOST}:{TTN_PORT}"
    )
    print(
        f"DB            : "
        f"{DB_PATH}"
    )
    print(
        f"ACK timeout   : "
        f"{ACK_TIMEOUT} s"
    )
    print("")

    init_db()

    threads = [
        threading.Thread(
            target=local_receiver,
            daemon=True
        ),

        threading.Thread(
            target=downstream_receiver,
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