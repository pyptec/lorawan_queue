"""SQLite fixtures only; no production DB or radio operations."""
import base64
from contextlib import closing
import hashlib
import json
import sqlite3
import unittest
from unittest.mock import patch
import test_device_aliases as alias_fixture
import test_device_sessions as session_fixture
from dashboard import queue_monitor, device_sessions


class SessionSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.fixture=alias_fixture.AliasIntegrationTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def test_full_decoder_join_and_data_consolidate_without_db_writes(self):
        frame=bytes(9)+bytes.fromhex(session_fixture.WATER)[::-1]+bytes(6)
        with closing(sqlite3.connect(self.fixture.path)) as db, db:
            raw=db.execute("SELECT raw_packet FROM uplink_queue").fetchone()[0]
            body=json.loads(raw[12:])
            body["rxpk"].append({"data":base64.b64encode(frame).decode()})
            db.execute("UPDATE uplink_queue SET raw_packet=?, received_at=?",(bytes(12)+json.dumps(body).encode(),session_fixture.stamp(session_fixture.NOW-10)))
        before=hashlib.sha256(self.fixture.path.read_bytes()).digest()
        registry=device_sessions.SessionRegistry([session_fixture.record(session_fixture.WATER,"009356D5")])
        with patch.object(queue_monitor,"load_sessions",return_value=registry):
            sample=queue_monitor.snapshot(self.fixture.path)
        self.assertEqual(sample["state"],"OK")
        self.assertEqual(len(sample["devices"]),4)
        water=next(item for item in sample["devices"] if item.get("dev_eui")==session_fixture.WATER)
        self.assertEqual(water["observation_count"],2)
        self.assertEqual(water["fport"],100)
        self.assertEqual(sample["device_summary"]["physical_device_count"],3)
        self.assertEqual(hashlib.sha256(self.fixture.path.read_bytes()).digest(),before)

    def test_same_address_old_and_new_owner_not_deduplicated_before_matching(self):
        frame=self.fixture.frames[0]
        packet=bytes(12)+json.dumps({"rxpk":[{"data":base64.b64encode(frame).decode()}]}).encode()
        with closing(sqlite3.connect(self.fixture.path)) as db, db:
            db.execute("DELETE FROM uplink_queue")
            for index,ago in ((1,100),(2,10)):
                db.execute("INSERT INTO uplink_queue VALUES (?,?,?,?,?)",(index,session_fixture.stamp(session_fixture.NOW-ago),"pending",0,packet))
        registry=device_sessions.SessionRegistry([session_fixture.record(session_fixture.LILY,"009356D5",session_fixture.NOW-1000,session_fixture.NOW-60),session_fixture.record(session_fixture.DRAGINO,"009356D5",session_fixture.NOW-60)])
        with patch.object(queue_monitor,"load_sessions",return_value=registry):
            sample=queue_monitor.snapshot(self.fixture.path)
        self.assertEqual(len(sample["devices"]),2)
        self.assertEqual({item["dev_eui"] for item in sample["devices"]},{session_fixture.LILY,session_fixture.DRAGINO})

    def test_session_load_after_read_lock_closed_and_missing_config_degrades_only_correlation(self):
        def load():
            with closing(sqlite3.connect(self.fixture.path,timeout=0.01)) as db, db:
                db.execute("BEGIN EXCLUSIVE")
                db.rollback()
            return device_sessions.load_sessions(self.fixture.path.with_name("missing-sessions.json"))
        with patch.object(queue_monitor,"load_sessions",side_effect=load):
            sample=queue_monitor.snapshot(self.fixture.path)
        self.assertEqual(sample["state"],"OK")
        self.assertEqual(sample["device_summary"]["session_config_state"],"UNKNOWN")
        self.assertEqual(len(sample["devices"]),4)


class SessionCacheFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_queue_sampler_invalidates_old_device_summary(self):
        import asyncio
        from types import SimpleNamespace
        from dashboard import app as web
        app=SimpleNamespace(state=SimpleNamespace(snapshot={"device_summary":{"state":"OK","active_device_count":3}}))
        def failed():
            raise OSError("synthetic failure")
        task=asyncio.create_task(web.poll(app,failed,interval=60))
        try:
            for _ in range(100):
                if app.state.snapshot.get("queue",{}).get("state")=="UNKNOWN":
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(app.state.snapshot["device_summary"]["state"],"UNKNOWN")
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
