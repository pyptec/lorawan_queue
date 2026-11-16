import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from . import queue_monitor, system_monitor, gateway_monitor, ups_monitor

ROOT = Path(__file__).parent
DB_PATH = os.environ.get("DASHBOARD_DB_PATH", "/home/pi/lorawan_queue/lorawan_queue.db")


def collect():
    """Solo SQLite; no depende de DNS, servicios ni recursos del sistema."""
    queue = queue_monitor.snapshot(DB_PATH)
    return {"queue": queue, "devices": queue["devices"]}


def merge(app, delta, source):
    data = dict(app.state.snapshot)
    data.update(delta)
    data["sampled_at"] = time.time()
    data["updated_at"] = {**data.get("updated_at", {}), source: data["sampled_at"]}
    data["gateway"] = gateway_monitor.snapshot(data.get("queue", {}), data.get("internet", {}))
    system = data.get("system", {})
    values = [system.get("cpu_percent"), system.get("ram", {}).get("percent"), system.get("disk", {}).get("percent")]
    measures = [system_monitor.level(value) for value in values]
    temp = system.get("temperature_c")
    measures.append("UNKNOWN" if temp is None else "CRITICAL" if temp >= 80 else "WARNING" if temp >= 70 else "OK")
    services = data.get("services", [])
    critical = "CRITICAL" in measures or any(s["state"] == "OFFLINE" for s in services)
    summary = data.get("queue", {}).get("summary", {})
    unknown = any(g["state"] not in ("OK", "ONLINE") for g in data["gateway"].values())
    degraded = unknown or any(m != "OK" for m in measures) or len(services) != 3 or any(s["state"] != "OK" for s in services)
    degraded = degraded or data.get("queue", {}).get("state") != "OK" or data.get("internet", {}).get("state") != "ONLINE"
    degraded = degraded or bool(summary.get("pending") or summary.get("failed"))
    data["health"] = "CRITICAL" if critical else "DEGRADED" if degraded else "OK"
    app.state.snapshot = data


async def poll(app, read=collect, section=None, interval=10):
    source = section or "queue"
    while True:
        try:
            sample = await asyncio.to_thread(read)
            delta = {section: sample} if section else sample
        except Exception:
            delta = {section: {"state": "UNKNOWN", "error": "Fuente no disponible"}} if section else {"queue": {"state": "UNKNOWN", "rows": [], "devices": []}, "devices": []}
            if section == "services":
                delta = {"services": [{"name": name, "state": "UNKNOWN"} for name in gateway_monitor.SERVICES]}
        merge(app, delta, source)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app):
    app.state.snapshot = {"health": "DEGRADED", "state": "UNKNOWN", "sampled_at": None,
        "queue": {"state": "UNKNOWN", "rows": [], "devices": []}, "devices": [],
        "internet": {"state": "UNKNOWN"}, "services": [], "ups": ups_monitor.unknown()}
    tasks = [asyncio.create_task(poll(app, collect)),
             asyncio.create_task(poll(app, system_monitor.snapshot, "system", 5)),
             asyncio.create_task(poll(app, gateway_monitor.services, "services", 15)),
             asyncio.create_task(poll(app, gateway_monitor.internet, "internet", 15)),
             asyncio.create_task(poll(app, ups_monitor.snapshot, "ups", 5))]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

app = FastAPI(title="SAMEE Gateway", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
async def index():
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/api/status")
async def status():
    return app.state.snapshot


def endpoint(section):
    async def get_section():
        return app.state.snapshot.get(section, {"state": "UNKNOWN"})
    return get_section

for section in ("system", "queue", "devices", "gateway", "services", "ups"):
    app.add_api_route("/api/" + section, endpoint(section), methods=["GET"])


@app.websocket("/ws/status")
async def websocket(ws: WebSocket):
    origin = ws.headers.get("origin")
    if origin and origin not in ("http://" + ws.headers.get("host", ""), "https://" + ws.headers.get("host", "")):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            await asyncio.wait_for(ws.send_json(app.state.snapshot), timeout=3)
            await asyncio.sleep(2)
    except (WebSocketDisconnect, OSError, RuntimeError, asyncio.TimeoutError):
        pass
