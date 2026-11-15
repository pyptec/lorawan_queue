"""Cada fuente puede faltar sin invalidar las demas metricas."""
import os
import socket
import time
from pathlib import Path
import psutil


def level(value):
    return "UNKNOWN" if value is None else "CRITICAL" if value > 85 else "WARNING" if value >= 70 else "OK"


def optional(read):
    try:
        return read()
    except (OSError, psutil.Error, ValueError, NotImplementedError, AttributeError):
        return None


def snapshot():
    memory = optional(psutil.virtual_memory)
    disk = optional(lambda: psutil.disk_usage(os.environ.get("DASHBOARD_DISK_PATH", Path.cwd().anchor)))
    temperature = optional(lambda: float(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000)
    frequency = optional(psutil.cpu_freq)
    interfaces = []
    stats = optional(psutil.net_if_stats)
    addresses_by_interface = optional(psutil.net_if_addrs)
    if stats is not None and addresses_by_interface is not None:
        for name, addresses in addresses_by_interface.items():
            for address in addresses:
                if address.family == socket.AF_INET and not address.address.startswith("127.") and stats.get(name) and stats[name].isup:
                    interfaces.append({"interface": name, "ip": address.address})
    boot = optional(psutil.boot_time)
    # Medicion acotada: evita la primera muestra indefinida de cpu_percent(None)
    # al alternar hilos del executor. No se ejecuta en el hilo ASGI ni en el proxy.
    cpu = optional(lambda: psutil.cpu_percent(interval=0.1))
    return {"source": "psutil / Linux sysfs", "hostname": optional(socket.gethostname),
            "time": time.time(), "uptime_seconds": max(0, time.time()-boot) if boot is not None else None,
            "cpu_percent": cpu, "temperature_c": temperature,
            "frequency_mhz": frequency.current if frequency else None,
            "load": optional(lambda: list(os.getloadavg())) if hasattr(os, "getloadavg") else None,
            "ram": {key: getattr(memory, key, None) for key in ("total", "used", "free", "available", "percent")},
            "disk": {key: getattr(disk, key, None) for key in ("total", "used", "free", "percent")},
            "lan": interfaces if stats is not None and addresses_by_interface is not None else None,
            "lan_state": "ONLINE" if interfaces else "OFFLINE" if stats is not None and addresses_by_interface is not None else "UNKNOWN",
            "network_gateway": "NO DISPONIBLE"}
