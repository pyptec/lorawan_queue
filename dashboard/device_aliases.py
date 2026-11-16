"""Local display aliases, never session inference or application payload decoding."""
import json
from pathlib import Path
import re

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "device_aliases.json"
UNREGISTERED = "DISPOSITIVO NO REGISTRADO"


def identifier(value, kind):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if kind == "device_id":
        return value.lower() if value and len(value) <= 200 else None
    value = re.sub(r"[\s:-]", "", value).upper()
    size = 16 if kind == "dev_eui" else 8
    return value if re.fullmatch(r"[0-9A-F]{%d}" % size, value) else None


class AliasRegistry:
    def __init__(self, entries=()):
        self.indexes = {key: {} for key in ("dev_eui", "device_id", "dev_addr")}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip() or len(name) > 200:
                continue
            alias = {"name": name.strip(), "description": None}
            description = entry.get("description")
            if isinstance(description, str) and len(description) <= 500:
                alias["description"] = description.strip() or None
            for kind in self.indexes:
                alias[kind] = identifier(entry.get(kind), kind)
            for kind, index in self.indexes.items():
                value = alias[kind]
                if value:
                    # Duplicate keys are ambiguous: never pick a name by file order.
                    index[value] = None if value in index else alias

    def resolve(self, device):
        result = dict(device)
        observed = {kind: identifier(device.get(kind), kind) for kind in self.indexes}
        identity = device.get("identity")
        if isinstance(identity, str):
            for prefix, kind in (("DevEUI:", "dev_eui"), ("DevAddr:", "dev_addr")):
                if identity.startswith(prefix) and not observed[kind]:
                    observed[kind] = identifier(identity[len(prefix):], kind)
        # These fields describe observations only, never copied from configuration.
        for kind, value in observed.items():
            if value is not None:
                result[kind] = value
        result.update(name=UNREGISTERED, registered=False, alias_match=None,
                      description=None, alias_device_id=None, alias_dev_eui=None,
                      alias_dev_addr=None)
        # A stronger observed identifier with no match must not be overridden by
        # an old session DevAddr. No learning from joins, FPort, RSSI or FCnt.
        for kind in ("dev_eui", "device_id", "dev_addr"):
            value = observed[kind]
            if value:
                alias = self.indexes[kind].get(value)
                if alias:
                    result.update(name=alias["name"], registered=True, alias_match=kind,
                                  description=alias["description"],
                                  alias_device_id=alias["device_id"],
                                  alias_dev_eui=alias["dev_eui"],
                                  alias_dev_addr=alias["dev_addr"])
                break
        return result


def load_registry(path=None):
    """Read once per queue sample, after SQLite has closed; fail to empty aliases."""
    try:
        with Path(path if path is not None else CONFIG_PATH).open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            return AliasRegistry()
        data = json.loads(raw.decode("utf-8-sig"))
        entries = data.get("devices") if isinstance(data, dict) else None
        if not isinstance(entries, list) or len(entries) > 256:
            return AliasRegistry()
        return AliasRegistry(entries)
    except (OSError, ValueError, TypeError, RecursionError):
        return AliasRegistry()
