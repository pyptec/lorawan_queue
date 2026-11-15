import asyncio
import base64
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from dashboard import app as web, queue_monitor, system_monitor, gateway_monitor


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "queue.db"
        frame = bytes([0x40,1,2,3,4,0,7,0,100,22,0,0,0,0])
        packet = bytes([2,0,1,0])+bytes(8)+json.dumps({"rxpk":[
            {"data":base64.b64encode(frame).decode(),"freq":915.2,"rssi":-90,"lsnr":7},
            {"data":"invalid", "freq":915.4}]}).encode()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE uplink_queue (id INTEGER PRIMARY KEY, received_at TEXT, status TEXT, attempts INTEGER, raw_packet BLOB, ack_at TEXT)")
            for i,status in enumerate(("sent","pending","failed"),1):
                db.execute("INSERT INTO uplink_queue VALUES (?,?,?,?,?,?)",(i,"2026-11-15T00:00:00+00:00",status,i,packet,"2026-11-15T00:00:01+00:00"))

    def tearDown(self):
        self.temp.cleanup()

    def test_sqlite_counts_readonly_and_multi_rxpk(self):
        before=hashlib.sha256(self.path.read_bytes()).digest()
        data=queue_monitor.snapshot(self.path)
        self.assertEqual(data["state"],"OK")
        self.assertEqual(data["summary"]["pending"],1)
        self.assertEqual(data["summary"]["sent"],1)
        self.assertEqual(data["summary"]["failed"],1)
        self.assertEqual(data["summary"]["attempts"],6)
        self.assertGreater(len(data["devices"]),1)
        self.assertEqual(data["devices"][0]["fport"],100)
        self.assertEqual(data["devices"][0]["fcnt16"],7)
        self.assertNotIn("raw_packet",data["rows"][0])
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).digest(),before)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[self.path])

    def test_missing_database_not_created(self):
        path=self.path.with_name("missing.db")
        self.assertEqual(queue_monitor.snapshot(path)["state"],"UNKNOWN")
        self.assertFalse(path.exists())

    def test_busy_database_degrades(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN EXCLUSIVE")
            self.assertEqual(queue_monitor.snapshot(self.path)["state"],"UNKNOWN")

    def test_system_and_thresholds(self):
        data=system_monitor.snapshot()
        self.assertGreater(data["ram"]["total"],0)
        self.assertGreater(data["disk"]["total"],0)
        for val,state in ((None,"UNKNOWN"),(69,"OK"),(70,"WARNING"),(86,"CRITICAL")):
            self.assertEqual(system_monitor.level(val),state)

    def test_services_linux(self):
        from subprocess import CompletedProcess
        output="LoadState=loaded\nActiveState=active\nMainPID=123\nNRestarts=2\n"
        with patch.object(gateway_monitor.sys,"platform","linux"), patch.object(gateway_monitor.subprocess,"run",return_value=CompletedProcess([],0,output)):
            self.assertTrue(all(s["state"]=="OK" for s in gateway_monitor.services()))
        with patch.object(gateway_monitor.sys,"platform","win32"):
            self.assertTrue(all(s["state"]=="UNKNOWN" for s in gateway_monitor.services()))

    def test_internet_failure_and_success(self):
        with patch.object(gateway_monitor.sys,"platform","linux"), patch.object(gateway_monitor.socket,"create_connection",side_effect=OSError), patch.object(gateway_monitor.subprocess,"run",side_effect=gateway_monitor.subprocess.CalledProcessError(1,[])):
            self.assertEqual(gateway_monitor.internet()["state"],"OFFLINE")
        with patch.object(gateway_monitor.sys,"platform","linux"), patch.object(gateway_monitor.socket,"create_connection"), patch.object(gateway_monitor.subprocess,"run"):
            self.assertEqual(gateway_monitor.internet()["state"],"ONLINE")

    def test_ttn_ack_not_internet(self):
        from datetime import datetime,timezone,timedelta
        now=datetime.now(timezone.utc)
        self.assertEqual(gateway_monitor.snapshot({"last_ack":now.isoformat()}, {"state":"ONLINE"})["ttn"]["state"],"ONLINE")
        self.assertEqual(gateway_monitor.snapshot({"last_ack":(now-timedelta(hours=1)).isoformat()}, {"state":"ONLINE"})["ttn"]["state"],"STALE")
        self.assertEqual(gateway_monitor.snapshot({})["ttn"]["state"],"UNKNOWN")

    def test_api_static_websocket_shared_cache(self):
        sample={"health":"DEGRADED","queue":{"state":"OK"},"sampled_at":1}
        with patch.object(web,"collect",return_value=sample) as collect, patch.object(web,"poll",new=AsyncMock()):
            with TestClient(web.app) as client:
                self.assertEqual(client.get("/").status_code,200)
                self.assertEqual(client.get("/static/js/dashboard.js").status_code,200)
                # Lifespan starts sampling asynchronously; use the explicit shared snapshot.
                web.app.state.snapshot=sample
                self.assertEqual(client.get("/api/status").json()["health"],"DEGRADED")
                self.assertEqual(client.get("/api/queue").json()["state"],"OK")
                self.assertEqual(client.post("/api/queue").status_code,405)
                with client.websocket_connect("/ws/status") as ws:
                    self.assertEqual(ws.receive_json()["sampled_at"],1)
                self.assertLessEqual(collect.call_count,1)

    def test_websocket_rejects_external_origin(self):
        from starlette.websockets import WebSocketDisconnect
        with patch.object(web,"poll",new=AsyncMock()):
            with TestClient(web.app) as client:
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect("/ws/status",headers={"origin":"https://external.invalid"}):
                        pass

    def test_missing_metrics_are_independent(self):
        with patch.object(system_monitor.psutil,"cpu_freq",side_effect=OSError), patch.object(system_monitor.psutil,"disk_usage",side_effect=PermissionError), patch.object(system_monitor.os,"getloadavg",side_effect=OSError,create=True):
            data=system_monitor.snapshot()
        self.assertIsNone(data["frequency_mhz"])
        self.assertIsNone(data["disk"]["percent"])
        self.assertIsNone(data["load"])
        self.assertGreater(data["ram"]["total"],0)

    def test_services_missing_property_is_unknown(self):
        from subprocess import CompletedProcess
        with patch.object(gateway_monitor.sys,"platform","linux"), patch.object(gateway_monitor.subprocess,"run",return_value=CompletedProcess([],0,"LoadState=loaded\n")):
            item=gateway_monitor.services()[0]
        self.assertEqual(item["state"],"UNKNOWN")
        self.assertEqual(item["ActiveState"],"UNKNOWN")

    def test_dns_fallback_and_timeout(self):
        from subprocess import CompletedProcess, TimeoutExpired
        with patch.object(gateway_monitor.sys,"platform","linux"), patch.object(gateway_monitor.socket,"create_connection"), patch.object(gateway_monitor.subprocess,"run",side_effect=[FileNotFoundError(),CompletedProcess([],0)]):
            data=gateway_monitor.internet()
            self.assertEqual(data["state"],"ONLINE")
            self.assertEqual(data["dns_source"],"Python getaddrinfo aislado")
        with patch.object(gateway_monitor.sys,"platform","linux"), patch.object(gateway_monitor.socket,"create_connection",side_effect=OSError), patch.object(gateway_monitor.subprocess,"run",side_effect=TimeoutExpired([],0.75)):
            self.assertEqual(gateway_monitor.internet()["state"],"UNKNOWN")

    def test_ttn_network_and_clock_cases(self):
        from datetime import datetime,timezone,timedelta
        recent=datetime.now(timezone.utc).isoformat()
        self.assertEqual(gateway_monitor.snapshot({"last_ack":recent},{"state":"OFFLINE"})["ttn"]["state"],"OFFLINE")
        self.assertEqual(gateway_monitor.snapshot({"last_ack":recent},{"state":"UNKNOWN"})["ttn"]["state"],"UNKNOWN")
        future=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        for stamp in (future,"not-a-date","2026-11-15T12:00:00",None):
            self.assertEqual(gateway_monitor.snapshot({"last_ack":stamp},{"state":"ONLINE"})["ttn"]["state"],"UNKNOWN")

    def test_malformed_packet_does_not_hide_good_devices(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            for i,payload in enumerate((b'[]',b'null',b'1',b'{"rxpk":[null,{}, {"data":3}]}'),4):
                db.execute("INSERT INTO uplink_queue VALUES (?,?,?,?,?,?)",(i,"x","pending",0,bytes(12)+payload,None))
        data=queue_monitor.snapshot(self.path)
        self.assertEqual(data["state"],"OK")
        self.assertTrue(any(d.get("fport")==100 for d in data["devices"]))
        self.assertTrue(all(d["model"]=="UNKNOWN DEVICE" for d in data["devices"]))

    def test_row_limit_and_sql_readonly(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany("INSERT INTO uplink_queue VALUES (?,?,?,?,?,?)",[(i,"x","pending",0,b'',None) for i in range(4,140)])
        original=sqlite3.connect
        queries=[]
        def connect(database,**kwargs):
            self.assertIn("mode=ro",database)
            self.assertTrue(kwargs["uri"])
            conn=original(database,**kwargs)
            conn.set_trace_callback(queries.append)
            return conn
        with patch.object(queue_monitor.sqlite3,"connect",side_effect=connect):
            data=queue_monitor.snapshot(self.path)
        self.assertEqual(len(data["rows"]),100)
        self.assertIn("PRAGMA query_only=ON",queries)
        self.assertFalse(any(q.lstrip().split()[0].upper() in {"CREATE","INSERT","UPDATE","DELETE","ALTER","VACUUM"} for q in queries))

    def test_decode_after_read_lock_released(self):
        from dashboard.device_decoder import decode_packet
        def decode(raw,row):
            with closing(sqlite3.connect(self.path,timeout=0.01)) as writer, writer:
                writer.execute("BEGIN EXCLUSIVE")
                writer.rollback()
            return decode_packet(raw,row)
        with patch.object(queue_monitor,"decode_packet",side_effect=decode):
            self.assertEqual(queue_monitor.snapshot(self.path)["state"],"OK")

    def test_missing_db_api_does_not_create_file(self):
        path=Path(self.temp.name)/"absent.db"
        with patch.object(web,"DB_PATH",str(path)),patch.object(web,"poll",new=AsyncMock()):
            with TestClient(web.app) as client:
                web.merge(web.app,web.collect(),"queue")
                result=client.get("/api/queue")
                self.assertEqual(result.status_code,200)
                self.assertEqual(result.json()["state"],"UNKNOWN")
                self.assertNotIn("summary",result.json())
        self.assertFalse(path.exists())


class SamplerTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_network_does_not_delay_local_queue(self):
        import threading
        from types import SimpleNamespace
        started=threading.Event()
        release=threading.Event()
        app=SimpleNamespace(state=SimpleNamespace(snapshot={}))
        def network():
            started.set()
            release.wait(2)
            return {"state":"UNKNOWN"}
        slow=asyncio.create_task(web.poll(app,network,"internet",60))
        local=asyncio.create_task(web.poll(app,lambda:{"queue":{"state":"OK"},"devices":[]},interval=60))
        try:
            for _ in range(100):
                if app.state.snapshot.get("queue",{}).get("state")=="OK" and started.is_set():break
                await asyncio.sleep(0.01)
            self.assertEqual(app.state.snapshot["queue"]["state"],"OK")
            self.assertNotIn("internet",app.state.snapshot)
            self.assertFalse(release.is_set())
        finally:
            release.set()
            slow.cancel();local.cancel()
            await asyncio.gather(slow,local,return_exceptions=True)
