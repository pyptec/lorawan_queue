"""Consolidate only observed permanent IDs or explicitly confirmed, timed sessions.
No join/uplink timing heuristic, root keys, TTN calls or runtime config writes.
"""
from datetime import datetime
import json
from pathlib import Path
import time
from .device_aliases import identifier

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "device_sessions.json"
ACTIVE_SECONDS = 120


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.timestamp() if stamp.tzinfo is not None else None
    except (ValueError, OverflowError, OSError):
        return None


class SessionRegistry:
    def __init__(self, entries=(), state="OK"):
        self.state = state
        records = []
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("confirmed") is not True:
                continue
            eui, addr = identifier(entry.get("dev_eui"), "dev_eui"), identifier(entry.get("dev_addr"), "dev_addr")
            start = timestamp(entry.get("valid_from"))
            end = timestamp(entry.get("valid_to")) if entry.get("valid_to") is not None else float("inf")
            evidence = entry.get("evidence")
            if not eui or not addr or start is None or end is None or end <= start:
                continue
            if not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 500:
                continue
            records.append({"dev_eui": eui, "dev_addr": addr, "start": start, "end": end, "evidence": evidence.strip()})
        # Fail closed on overlapping assignments of the same address, even duplicates.
        ambiguous = set()
        for i, left in enumerate(records):
            for j in range(i + 1, len(records)):
                right = records[j]
                if left["dev_addr"] == right["dev_addr"] and max(left["start"], right["start"]) < min(left["end"], right["end"]):
                    ambiguous.update((i, j))
        self.records = [record for i, record in enumerate(records) if i not in ambiguous]
        self.ambiguous_records = len(ambiguous)

    def match(self, address, observed_at):
        if observed_at is None:
            return None
        return next((r for r in self.records if r["dev_addr"] == address and r["start"] <= observed_at < r["end"]), None)

    def history(self, eui, now):
        records = [r for r in self.records if r["dev_eui"] == eui and r["start"] <= now]
        current = [r for r in records if now < r["end"]]
        address = current[0]["dev_addr"] if len(current) == 1 else None
        previous = sorted({r["dev_addr"] for r in records if r["end"] <= now and r["dev_addr"] != address})
        return address, previous


def load_sessions(path=None):
    try:
        with Path(path if path is not None else CONFIG_PATH).open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("size")
        data = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("sessions"), list) or len(data["sessions"]) > 256:
            raise ValueError("schema")
        return SessionRegistry(data["sessions"])
    except (OSError, ValueError, TypeError, RecursionError):
        return SessionRegistry(state="UNKNOWN")


def _order(item):
    stamp = timestamp(item.get("received_at"))
    packet = item.get("packet_id")
    index = item.get("rxpk_index")
    return (stamp if stamp is not None else float("-inf"), packet if isinstance(packet, int) else -1, -index if isinstance(index, int) else 0)


def consolidate(observations, aliases, sessions, now=None):
    now = time.time() if now is None else now
    groups, identities = {}, set()
    for index, raw in enumerate(observations):
        item = aliases.resolve(raw)
        observed_eui, address = item.get("dev_eui"), item.get("dev_addr")
        eui = observed_eui
        source = "observed_dev_eui" if eui else "unassociated"
        match = None
        if not eui and item.get("alias_match") == "device_id" and item.get("alias_dev_eui"):
            eui, source = item["alias_dev_eui"], "configured_device_id"
        if not eui and not item.get("device_id") and address:
            match = sessions.match(address, timestamp(item.get("received_at")))
            if match:
                eui, source = match["dev_eui"], "confirmed_session"
                item = aliases.resolve({**item, "dev_eui": eui})
        observed_identity = raw.get("identity") or "unknown:%s:%s:%s" % (raw.get("packet_id"), raw.get("rxpk_index"), index)
        identities.add(observed_identity)
        key = "DevEUI:" + eui if eui else "DeviceID:" + item["device_id"] if item.get("device_id") else observed_identity
        group = groups.setdefault(key, {"items": [], "observed_identities": set(), "observed_euis": set(), "addresses": set(), "sources": set(), "evidence": set(), "eui": eui})
        group["items"].append(item)
        group["observed_identities"].add(observed_identity)
        group["sources"].add(source)
        if observed_eui:
            group["observed_euis"].add(observed_eui)
        if address:
            group["addresses"].add(address)
        if match:
            group["evidence"].add(match["evidence"])
    entities, latest_uplinks = [], []
    for key, group in groups.items():
        items = group["items"]
        latest = max(items, key=_order)
        uplinks = [item for item in items if item.get("frame_type") == "UPLINK"]
        uplink = max(uplinks, key=_order) if uplinks else None
        # A later Join Request must not erase the last data-frame telemetry.
        entity = dict(uplink if uplink is not None else latest)
        permanent = key.startswith(("DevEUI:", "DeviceID:"))
        current, previous = sessions.history(group["eui"], now) if group["eui"] else (None, [])
        last_seen = latest.get("received_at") if timestamp(latest.get("received_at")) is not None else None
        uplink_stamp = timestamp(uplink.get("received_at")) if uplink else None
        active = uplink_stamp is not None and 0 <= now - uplink_stamp <= ACTIVE_SECONDS
        entity.update(identity=key, entity_key=key, correlated=permanent,
                      dev_eui=group["eui"] if group["eui"] else entity.get("dev_eui"),
                      observed_dev_euis=sorted(group["observed_euis"]),
                      observed_identities=sorted(group["observed_identities"]),
                      observed_dev_addrs=sorted(group["addresses"]),
                      correlation_sources=sorted(group["sources"]), session_evidence=sorted(group["evidence"]),
                      current_dev_addr=current, previous_dev_addrs=previous,
                      last_seen=last_seen, received_at=last_seen,
                      last_uplink_at=uplink.get("received_at") if uplink else None,
                      last_fport=uplink.get("fport") if uplink else None,
                      last_fcnt=uplink.get("fcnt16") if uplink else None,
                      active=active, observation_count=len(items),
                      join_request_count=sum(item.get("frame_type") == "JOIN_REQUEST" for item in items))
        if group["eui"] is None and "dev_eui" not in latest:
            entity.pop("dev_eui", None)
        entities.append(entity)
        if uplink_stamp is not None:
            latest_uplinks.append((uplink_stamp, entity))
    entities.sort(key=lambda item: _order({**item, "received_at": item.get("last_seen")}), reverse=True)
    last = max(latest_uplinks, key=lambda pair: pair[0])[1] if latest_uplinks else None
    summary = {"state": "OK", "sampled_at": now, "active_window_seconds": ACTIVE_SECONDS,
               "observed_identity_count": len(identities), "entity_count": len(entities),
               "physical_device_count": sum(item["correlated"] for item in entities),
               "uncorrelated_identity_count": sum(not item["correlated"] for item in entities),
               "registered_count": sum(item["registered"] for item in entities),
               "active_device_count": sum(item["active"] and item["correlated"] for item in entities),
               "active_uncorrelated_count": sum(item["active"] and not item["correlated"] for item in entities),
               "visible_count": min(len(entities), 100), "truncated": len(entities) > 100,
               "session_config_state": sessions.state, "ambiguous_session_records": sessions.ambiguous_records,
               "correlation_mode": "confirmed_configuration_only",
               "latest_uplink": {"name": last["name"] if last["registered"] else None,
                                 "identity": last["identity"], "dev_addr": last.get("dev_addr"),
                                 "received_at": last["last_uplink_at"]} if last else None}
    return entities[:100], summary
