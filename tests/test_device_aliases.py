"""Local alias tests: synthetic frames and temporary SQLite only."""
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
from dashboard import device_aliases as aliases, queue_monitor, app as web


def fixture_device(dev_addr="009356D5", dev_eui=None):
    return {"identity": "DevEUI:" + dev_eui if dev_eui else "DevAddr:" + dev_addr,
            "fport":100,"fcnt16":84,"rssi":-87,"lsnr":8.5}


class AliasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "aliases.json"

    def tearDown(self):
        self.temp.cleanup()

    def load(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return aliases.load_registry(self.path)

    def test_initial_configuration(self):
        registry = aliases.load_registry()
        expected = (("70B3D57ED0079EC3", "LILYGO T3S3"), ("A84041D1B186E98A", "Dragino LHT65N"), ("8C83FC05009356D5", "QALCOSONIC W1"))
        for eui, name in expected:
            self.assertEqual(registry.resolve(fixture_device(dev_eui=eui))["name"], name)

    def test_known_devaddr_preserves_observations_and_marks_config_metadata(self):
        original = fixture_device()
        result = aliases.load_registry().resolve(original)
        self.assertEqual(result["name"], "QALCOSONIC W1")
        self.assertTrue(result["registered"])
        self.assertEqual(result["alias_match"], "dev_addr")
        self.assertEqual(result["dev_addr"], "009356D5")
        self.assertNotIn("dev_eui", result)
        self.assertNotIn("device_id", result)
        self.assertEqual(result["alias_dev_eui"], "8C83FC05009356D5")
        self.assertEqual(result["alias_device_id"], "calle3sur-103")
        for field in ("identity","fport","fcnt16","rssi","lsnr"):
            self.assertEqual(result[field], original[field])
        self.assertNotIn("name", original)

    def test_no_matching_by_fport_or_eui_suffix(self):
        for port in (10,100):
            result = aliases.load_registry().resolve({**fixture_device("ABCDEF12"), "fport":port})
            self.assertFalse(result["registered"])
            self.assertEqual(result["name"], aliases.UNREGISTERED)
        # Lilygo and Dragino have no known session address configured.
        for addr in ("D0079EC3","B186E98A"):
            self.assertFalse(aliases.load_registry().resolve(fixture_device(addr))["registered"])

    def test_unknown_without_identifier(self):
        self.assertEqual(aliases.load_registry().resolve({"fport":100})["name"], aliases.UNREGISTERED)

    def test_eui_has_priority_over_device_id_and_address(self):
        registry = aliases.load_registry()
        item = {**fixture_device(), "dev_eui":"70B3D57ED0079EC3", "device_id":"calle3sur-103"}
        result = registry.resolve(item)
        self.assertEqual(result["name"], "LILYGO T3S3")
        self.assertEqual(result["alias_match"], "dev_eui")

    def test_unknown_stronger_identifier_prevents_old_address_override(self):
        result = aliases.load_registry().resolve({**fixture_device(), "dev_eui":"FFFFFFFFFFFFFFFF"})
        self.assertFalse(result["registered"])
        result = aliases.load_registry().resolve({**fixture_device(), "device_id":"another-device"})
        self.assertFalse(result["registered"])

    def test_future_confirmed_device_id(self):
        result = aliases.load_registry().resolve({"device_id":"dragino-lht65n-jaime"})
        self.assertEqual(result["name"], "Dragino LHT65N")
        self.assertEqual(result["alias_match"], "device_id")
        self.assertNotIn("dev_eui", result)

    def test_hex_case_and_separators(self):
        result = aliases.load_registry().resolve({"dev_eui":"70:b3:d5:7e:d0:07:9e:c3"})
        self.assertEqual(result["name"], "LILYGO T3S3")
        self.assertEqual(result["dev_eui"], "70B3D57ED0079EC3")

    def test_missing_config(self):
        self.assertFalse(aliases.load_registry(self.path).resolve(fixture_device())["registered"])
        self.assertFalse(self.path.exists())

    def test_invalid_json_encoding_and_structure(self):
        for content in (b"{", b"\xff", b"null", b"[]", b'{"devices":null}', b'{"devices":{}}'):
            self.path.write_bytes(content)
            self.assertEqual(aliases.load_registry(self.path).resolve(fixture_device())["name"], aliases.UNREGISTERED)

    def test_empty_and_incomplete_entries(self):
        for data in ({}, {"devices":[]}, {"devices":[None, {}, {"dev_addr":"009356D5"}, {"name":3}]}):
            self.assertFalse(self.load(data).resolve(fixture_device())["registered"])
        result = self.load({"devices":[{"name":"Water meter", "dev_eui":"8C83FC05009356D5"}]}).resolve(fixture_device(dev_eui="8C83FC05009356D5"))
        self.assertEqual(result["name"], "Water meter")
        self.assertIsNone(result["description"])
        self.assertIsNone(result["alias_device_id"])
        self.assertIsNone(result["alias_dev_addr"])

    def test_ambiguous_duplicate_is_not_assigned(self):
        registry = self.load({"devices":[{"name":name,"dev_addr":"009356D5"} for name in ("One","Two","Three")]})
        self.assertFalse(registry.resolve(fixture_device())["registered"])

    def test_oversized_file_falls_back(self):
        self.path.write_bytes(b" " * 65537)
        self.assertFalse(aliases.load_registry(self.path).resolve(fixture_device())["registered"])

    def test_changed_config_reflected_next_sample(self):
        self.load({"devices":[{"name":"First","dev_addr":"009356D5"}]})
        self.assertEqual(aliases.load_registry(self.path).resolve(fixture_device())["name"],"First")
        self.load({"devices":[{"name":"Second","dev_addr":"009356D5"}]})
        self.assertEqual(aliases.load_registry(self.path).resolve(fixture_device())["name"],"Second")


class AliasIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fixture.db"
        def uplink(addr):
            return bytes([0x40]) + bytes.fromhex(addr)[::-1] + bytes([0,84,0,100,22,0,0,0,0])
        def join(eui):
            return bytes(9) + bytes.fromhex(eui)[::-1] + bytes(6)
        self.frames = [uplink("009356D5"), uplink("ABCDEF12"), join("70B3D57ED0079EC3"), join("A84041D1B186E98A")]
        packet = bytes(12) + json.dumps({"rxpk":[{"data":base64.b64encode(frame).decode(),"rssi":-87,"lsnr":8.5,"freq":915.2} for frame in self.frames]}).encode()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE uplink_queue (id INTEGER PRIMARY KEY,received_at TEXT,status TEXT,attempts INTEGER,raw_packet BLOB)")
            db.execute("INSERT INTO uplink_queue VALUES (1,?,?,?,?)",("2026-11-16T00:00:00+00:00","pending",0,packet))

    def tearDown(self):
        self.temp.cleanup()

    def test_names_from_actual_decoder_and_readonly_snapshot(self):
        before = hashlib.sha256(self.path.read_bytes()).digest()
        sample = queue_monitor.snapshot(self.path)
        self.assertEqual(sample["state"],"OK")
        self.assertEqual(len(sample["devices"]),4)
        self.assertEqual({d["name"] for d in sample["devices"]},{"QALCOSONIC W1","LILYGO T3S3","Dragino LHT65N",aliases.UNREGISTERED})
        water = next(d for d in sample["devices"] if d["name"]=="QALCOSONIC W1")
        self.assertEqual((water["dev_addr"],water["fport"],water["fcnt16"],water["rssi"],water["lsnr"]),("009356D5",100,84,-87,8.5))
        self.assertNotIn("dev_eui", water)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).digest(), before)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[self.path])

    def test_bad_or_missing_alias_file_does_not_break_queue(self):
        config = Path(self.temp.name) / "bad.json"
        for content in (None,"{"):
            if content is not None:
                config.write_text(content,encoding="utf-8")
            with patch.object(aliases,"CONFIG_PATH",config):
                sample = queue_monitor.snapshot(self.path)
            self.assertEqual(sample["state"],"OK")
            self.assertEqual(len(sample["devices"]),4)
            self.assertTrue(all(d["name"]==aliases.UNREGISTERED for d in sample["devices"]))

    def test_registry_load_occurs_after_sqlite_read_lock_closed(self):
        original = queue_monitor.load_registry
        def load():
            with closing(sqlite3.connect(self.path,timeout=0.01)) as writer, writer:
                writer.execute("BEGIN EXCLUSIVE")
                writer.rollback()
            return original()
        with patch.object(queue_monitor,"load_registry",side_effect=load):
            self.assertEqual(queue_monitor.snapshot(self.path)["state"],"OK")

    def test_cached_api_and_websocket_include_names(self):
        with patch.object(web,"poll",new=AsyncMock()), patch.object(web,"DB_PATH",str(self.path)):
            with TestClient(web.app) as client:
                web.merge(web.app,web.collect(),"queue")
                expected = web.app.state.snapshot["devices"]
                self.assertEqual(client.get("/api/devices").json(),expected)
                self.assertEqual(client.get("/api/status").json()["devices"],expected)
                with client.websocket_connect("/ws/status") as ws:
                    self.assertEqual(ws.receive_json()["devices"],expected)
