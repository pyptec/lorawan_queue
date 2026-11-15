"""Consultas acotadas sin importar el proxy ni cambiar su esquema."""
import sqlite3
import time
from pathlib import Path
from .device_decoder import decode_packet

COLUMNS = "id received_at original_time gateway_eui status attempts last_attempt sent_at ack_at delay_seconds created_at".split()


def snapshot(path, budget=0.08):
    result = {"state": "UNKNOWN", "source": "SQLite mode=ro", "rows": [], "devices": [],
              "autonomy": "NO DISPONIBLE", "error": None}
    conn = None
    try:
        path = Path(path).resolve()
        result["size_bytes"] = path.stat().st_size
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.02)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        deadline = time.monotonic() + budget
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        conn.execute("BEGIN")
        available = {r[1] for r in conn.execute("PRAGMA table_info(uplink_queue)")}
        if not {"id", "received_at", "status", "attempts", "raw_packet"} <= available:
            raise ValueError("schema")
        selected = ",".join(c if c in available else "NULL AS " + c for c in COLUMNS)
        result["rows"] = [dict(r) for r in conn.execute(
            "SELECT " + selected + " FROM uplink_queue ORDER BY id DESC LIMIT 100")]
        summary = dict(conn.execute("""SELECT COUNT(*) total,
            SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) sent,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) pending,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) failed,
            SUM(attempts) attempts, MIN(received_at) oldest, MAX(received_at) newest
            FROM uplink_queue""").fetchone())
        result["summary"] = {k: (v or 0) if k in ("sent", "pending", "failed", "attempts") else v for k,v in summary.items()}
        result["last_ack"] = conn.execute("SELECT MAX(ack_at) FROM uplink_queue").fetchone()[0] if "ack_at" in available else None
        devices = {}
        raw_rows = conn.execute("""SELECT id,received_at,status,
            CASE WHEN typeof(raw_packet)='blob' AND length(raw_packet)<=65535
                 THEN raw_packet ELSE NULL END AS raw_packet
            FROM uplink_queue ORDER BY id DESC LIMIT 100""").fetchall()
        # Liberar el read-lock ANTES de decodificar JSON/LoRaWAN.
        conn.close()
        conn = None
        for r in raw_rows:
            if r["raw_packet"] is None:
                continue
            for item in decode_packet(r["raw_packet"], r):
                key = item["identity"] or f"unknown:{r['id']}:{item['rxpk_index']}"
                devices.setdefault(key, item)
        result["devices"] = list(devices.values())[:100]
        result["state"] = "OK"
    except (OSError, sqlite3.Error, ValueError, TypeError):
        result.update(state="UNKNOWN", error="SQLite no disponible, incompatible, ocupada o presupuesto agotado")
    finally:
        if conn is not None:
            conn.close()
    return result
