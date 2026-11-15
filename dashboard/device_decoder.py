"""Metadata visible en PHYPayload; nunca descifra FRMPayload."""
import base64
import json
import struct


def decode_packet(raw, row):
    result = []
    try:
        body = json.loads(bytes(raw)[12:], parse_constant=lambda _: None)
        if not isinstance(body, dict):
            return []
        packets = body.get("rxpk", [])
        if not isinstance(packets, list):
            return []
        for index, rx in enumerate(packets[:64]):
            if not isinstance(rx, dict):
                continue
            item = {key: rx.get(key) if isinstance(rx.get(key), (str, int, float)) else None
                    for key in ("freq", "rssi", "lsnr", "datr", "time", "tmst")}
            item.update(packet_id=row["id"], rxpk_index=index, received_at=row["received_at"],
                        status=row["status"], identity=None, model="UNKNOWN DEVICE",
                        application_values="NO DISPONIBLE: payload cifrado; decoder/identidad no validados")
            try:
                frame = base64.b64decode(rx.get("data", ""), validate=True)
                mtype = frame[0] >> 5
                if mtype in (2, 4) and len(frame) >= 12 and 8 + (frame[5] & 15) <= len(frame) - 4:
                    item["identity"] = "DevAddr:" + frame[1:5][::-1].hex().upper()
                    item["fcnt16"] = struct.unpack_from("<H", frame, 6)[0]
                    port = 8 + (frame[5] & 15)
                    item["fport"] = frame[port] if port < len(frame) - 4 else None
                elif mtype == 0 and len(frame) == 23:
                    item["identity"] = "DevEUI:" + frame[9:17][::-1].hex().upper()
            except (ValueError, TypeError, IndexError):
                pass
            result.append(item)
    except (ValueError, TypeError, UnicodeError):
        pass
    return result
