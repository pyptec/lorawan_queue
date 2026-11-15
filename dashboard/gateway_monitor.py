import socket
import subprocess
import sys
from datetime import datetime, timezone

SERVICES = ("ttn-gateway.service", "lorawan-queue.service", "dashboard.service")


def services():
    result = []
    for name in SERVICES:
        item = {"name": name, "state": "UNKNOWN", "source": "systemctl show"}
        if sys.platform.startswith("linux"):
            try:
                process = subprocess.run(["systemctl", "show", name, "--no-pager",
                    "--property=LoadState,ActiveState,SubState,MainPID,ActiveEnterTimestamp,NRestarts,ActiveEnterTimestampMonotonic"],
                    capture_output=True, text=True, timeout=0.5, check=True)
                props = dict(line.split("=", 1) for line in process.stdout.splitlines() if "=" in line)
                if props.get("LoadState") == "loaded":
                    for prop in ("ActiveState", "SubState", "MainPID", "ActiveEnterTimestamp", "NRestarts"):
                        item[prop] = props.get(prop) or "UNKNOWN"
                    active = props.get("ActiveState")
                    item["state"] = "OK" if active == "active" else "OFFLINE" if active in ("inactive", "failed") else "UNKNOWN"
                    try:
                        from pathlib import Path
                        boot_seconds = float(Path("/proc/uptime").read_text().split()[0])
                        started = int(props.get("ActiveEnterTimestampMonotonic", 0)) / 1000000
                        item["uptime_seconds"] = max(0, boot_seconds-started) if started else None
                    except (OSError, ValueError, IndexError):
                        item["uptime_seconds"] = None
            except (OSError, subprocess.SubprocessError):
                pass
        result.append(item)
    return result


def internet():
    result = {"state": "UNKNOWN", "source": "TCP 1.1.1.1:443 + DNS TTN con plazo",
              "tcp": False, "dns": None, "dns_source": "UNKNOWN"}
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=0.5):
            result["tcp"] = True
    except OSError:
        pass
    dns = None
    if sys.platform.startswith("linux"):
        try:
            subprocess.run(["resolvectl", "query", "nam1.cloud.thethings.network"],
                           capture_output=True, timeout=0.75, check=True)
            dns = True
            result["dns_source"] = "resolvectl"
        except (OSError, subprocess.SubprocessError):
            pass
    if dns is None:
        # Proceso cancelable: getaddrinfo en un hilo no ofrece timeout efectivo.
        # Host fijo; sin shell, sin entrada del navegador ni salida de secretos.
        try:
            subprocess.run([sys.executable, "-c",
                "import socket; socket.getaddrinfo('nam1.cloud.thethings.network',1700)"],
                capture_output=True, timeout=0.75, check=True,
                **({"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}))
            dns = True
            result["dns_source"] = "Python getaddrinfo aislado"
        except subprocess.CalledProcessError:
            dns = False
            result["dns_source"] = "Python getaddrinfo aislado"
        except (OSError, subprocess.TimeoutExpired):
            pass
    result["dns"] = dns
    result["state"] = "ONLINE" if result["tcp"] and dns else "DEGRADED" if result["tcp"] or dns else "OFFLINE" if dns is False else "UNKNOWN"
    result["limitation"] = "Pruebas puntuales: un destino o DNS bloqueado no prueba caida universal de Internet"
    return result


def snapshot(queue, network=None):
    age = None
    try:
        stamp = datetime.fromisoformat(queue.get("last_ack").replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc)-stamp).total_seconds()
    except (ValueError, TypeError, AttributeError):
        pass
    network_state = (network or {}).get("state", "UNKNOWN")
    state = "UNKNOWN"
    if network_state == "OFFLINE":
        state = "OFFLINE"
    elif network_state == "ONLINE" and age is not None and age >= 0:
        state = "ONLINE" if age <= 120 else "STALE"
    return {"ttn": {"state": state,
                    "ack_age_seconds": age, "source": "SQLite ack_at; PUSH_ACK historico; no mide PULL_ACK ni entrega final",
                    "limitation": "ACK antiguo no demuestra desconexion; depende del trafico y reloj. OFFLINE se infiere solo de las pruebas Internet; no es una prueba UDP TTN"},
            "rak5146": {"state": "UNKNOWN", "source": "sin telemetria RF actual", "spi": "UNKNOWN", "plan": "AU915 FSB1 declarado por usuario; contraste PENDIENTE"},
            "gps": {"state": "UNKNOWN", "source": "sin fuente estable configurada"}}
