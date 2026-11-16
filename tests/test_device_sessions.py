"""Session evidence is synthetic: no mapping in these tests is production data."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from dashboard import device_sessions as sessions, device_aliases, device_decoder, queue_monitor, app as web

NOW = 1794830400.0
LILY = "70B3D57ED0079EC3"
DRAGINO = "A84041D1B186E98A"
WATER = "8C83FC05009356D5"


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def record(eui, addr, start=NOW-60, end=None):
    return {"dev_eui":eui,"dev_addr":addr,"valid_from":stamp(start),"valid_to":stamp(end) if end is not None else None,"confirmed":True,"evidence":"SYNTHETIC TEST ONLY: confirmed association fixture"}


def observation(identity, ago=10, join=False, **extra):
    return {"identity":identity,"received_at":stamp(NOW-ago),"frame_type":"JOIN_REQUEST" if join else "UPLINK","mtype":0 if join else 2,"packet_id":int(NOW-ago),"rxpk_index":0,"fport":None if join else 10,"fcnt16":None if join else 84,"rssi":-87,"lsnr":8.5,**extra}


def three_devices():
    records = [record(DRAGINO,"11111111"),record(LILY,"22222222"),record(LILY,"22222221",NOW-1000,NOW-60),record(WATER,"33333333"),record(WATER,"33333332",NOW-1000,NOW-60)]
    observations = [observation("DevEUI:"+eui,ago=5,join=True) for eui in (DRAGINO,LILY,WATER)]
    for entry in records:
        observations.append(observation("DevAddr:"+entry["dev_addr"],ago=100 if entry["valid_to"] else 10))
    return observations, sessions.SessionRegistry(records)


class SessionTests(unittest.TestCase):
    def collect(self, items, records=()):
        registry = records if isinstance(records,sessions.SessionRegistry) else sessions.SessionRegistry(records)
        return sessions.consolidate(items,device_aliases.load_registry(),registry,now=NOW)

    def test_dragino_join_and_confirmed_uplink_one_row(self):
        rows, summary = self.collect([observation("DevEUI:"+DRAGINO,join=True),observation("DevAddr:11111111")],[record(DRAGINO,"11111111")])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["name"],"Dragino LHT65N")
        self.assertEqual(rows[0]["current_dev_addr"],"11111111")
        self.assertEqual(rows[0]["observed_dev_euis"],[DRAGINO])
        self.assertIn("confirmed_session",rows[0]["correlation_sources"])
        self.assertEqual(summary["physical_device_count"],1)

    def test_lilygo_current_and_previous_one_row(self):
        items, registry = three_devices()
        rows, summary = self.collect(items,registry)
        lily = next(row for row in rows if row["dev_eui"]==LILY)
        self.assertEqual(lily["current_dev_addr"],"22222222")
        self.assertEqual(lily["previous_dev_addrs"],["22222221"])
        self.assertEqual(lily["observation_count"],3)
        self.assertEqual(len(rows),3)

    def test_water_session_update_preserves_name(self):
        items, registry = three_devices()
        rows, _ = self.collect(items,registry)
        water = next(row for row in rows if row["dev_eui"]==WATER)
        self.assertEqual(water["name"],"QALCOSONIC W1")
        self.assertEqual(water["current_dev_addr"],"33333333")
        self.assertEqual(water["previous_dev_addrs"],["33333332"])

    def test_kpi_three_devices_five_sessions(self):
        items, registry = three_devices()
        rows, summary = self.collect(items,registry)
        self.assertEqual((summary["physical_device_count"],summary["active_device_count"],summary["entity_count"]),(3,3,3))
        self.assertEqual(summary["observed_identity_count"],8)
        self.assertEqual(summary["uncorrelated_identity_count"],0)
        self.assertEqual(len(rows),3)

    def test_no_join_proximity_or_fport_inference(self):
        rows, summary = self.collect([observation("DevEUI:"+LILY,ago=11,join=True),observation("DevAddr:260CB888",fport=10),observation("DevAddr:260CA3CA",fport=10)])
        self.assertEqual(len(rows),3)
        unknown = [row for row in rows if not row["correlated"]]
        self.assertEqual(len(unknown),2)
        self.assertTrue(all(row["name"]==device_aliases.UNREGISTERED for row in unknown))
        self.assertEqual(summary["active_device_count"],0)
        self.assertEqual(summary["active_uncorrelated_count"],2)

    def test_confirmed_device_id_configuration_merges_with_eui(self):
        items=[observation("DevEUI:"+LILY,join=True),observation("DevAddr:ABCDEF12",device_id="lilygo-t3s3-test")]
        rows, summary=self.collect(items)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["name"],"LILYGO T3S3")
        self.assertIn("configured_device_id",rows[0]["correlation_sources"])
        self.assertEqual(summary["physical_device_count"],1)

    def test_expired_address_not_used_for_later_frame(self):
        rows, summary = self.collect([observation("DevAddr:11111111",ago=10)],[record(DRAGINO,"11111111",NOW-1000,NOW-100)])
        self.assertFalse(rows[0]["correlated"])
        self.assertEqual(summary["physical_device_count"],0)

    def test_reused_address_resolves_by_time(self):
        records = [record(LILY,"11111111",NOW-1000,NOW-60),record(DRAGINO,"11111111",NOW-60)]
        rows, summary = self.collect([observation("DevAddr:11111111",ago=100),observation("DevAddr:11111111",ago=10)],records)
        self.assertEqual({row["dev_eui"] for row in rows},{LILY,DRAGINO})
        self.assertEqual(summary["physical_device_count"],2)

    def test_overlapping_or_duplicate_assignments_fail_closed(self):
        for second in (LILY,DRAGINO):
            rows, summary = self.collect([observation("DevAddr:11111111")],[record(DRAGINO,"11111111"),record(second,"11111111")])
            self.assertFalse(rows[0]["correlated"])
            self.assertEqual(summary["ambiguous_session_records"],2)

    def test_current_address_ambiguous_when_same_device_has_two_open_sessions(self):
        rows, _ = self.collect([observation("DevEUI:"+LILY,join=True)],[record(LILY,"11111111"),record(LILY,"22222222")])
        self.assertIsNone(rows[0]["current_dev_addr"])

    def test_confirmation_evidence_and_aware_times_required(self):
        valid = record(LILY,"11111111")
        for change in ({"confirmed":False},{"evidence":""},{"valid_from":"2026-11-16T12:00:00"},{"valid_to":"invalid"},{"dev_eui":"bad"},{"valid_to":valid["valid_from"]}):
            rows, _ = self.collect([observation("DevAddr:11111111")],[{**valid,**change}])
            self.assertFalse(rows[0]["correlated"])

    def test_invalid_observation_time_does_not_correlate(self):
        rows, summary = self.collect([observation("DevAddr:11111111",received_at="invalid")],[record(LILY,"11111111")])
        self.assertFalse(rows[0]["correlated"])
        self.assertFalse(rows[0]["active"])
        self.assertIsNone(summary["latest_uplink"])

    def test_newer_join_does_not_erase_data_telemetry(self):
        rows, summary = self.collect([observation("DevEUI:"+LILY,ago=1,join=True),observation("DevAddr:11111111",ago=20,fport=10,fcnt16=84)],[record(LILY,"11111111")])
        self.assertEqual(rows[0]["last_fport"],10)
        self.assertEqual(rows[0]["last_fcnt"],84)
        self.assertEqual(rows[0]["fcnt16"],84)
        self.assertEqual(rows[0]["last_seen"],stamp(NOW-1))
        self.assertEqual(summary["latest_uplink"]["received_at"],stamp(NOW-20))

    def test_join_only_and_old_or_future_data_are_not_active(self):
        for item in (observation("DevEUI:"+LILY,join=True),observation("DevAddr:11111111",ago=121),observation("DevAddr:11111111",ago=-5)):
            rows, summary = self.collect([item],[record(LILY,"11111111",NOW-1000)])
            self.assertFalse(rows[0]["active"])
            self.assertEqual(summary["active_device_count"],0)

    def test_latest_unknown_uplink_identifies_address_not_port(self):
        rows, summary = self.collect([observation("DevAddr:ABCDEF12",fport=100)])
        self.assertEqual(rows[0]["name"],device_aliases.UNREGISTERED)
        self.assertIsNone(summary["latest_uplink"]["name"])
        self.assertEqual(summary["latest_uplink"]["dev_addr"],"ABCDEF12")

    def test_empty_configuration_and_no_runtime_learning(self):
        before = sessions.CONFIG_PATH.read_bytes()
        self.assertEqual(json.loads(before)["sessions"],[])
        self.collect([observation("DevEUI:"+LILY,join=True),observation("DevAddr:260CB888")])
        self.assertEqual(sessions.CONFIG_PATH.read_bytes(),before)

    def test_session_loader_absent_invalid_and_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"sessions.json"
            self.assertEqual(sessions.load_sessions(path).state,"UNKNOWN")
            for raw in (b"{",b"null",b"\xff",b'{"sessions":[]}',b" "*65537):
                path.write_bytes(raw)
                self.assertEqual(sessions.load_sessions(path).state,"UNKNOWN")
            path.write_text(json.dumps({"schema_version":1,"sessions":[record(LILY,"11111111")]}),encoding="utf-8")
            self.assertEqual(len(sessions.load_sessions(path).records),1)

    def test_no_permanent_identity_inferred_from_old_alias_devaddr(self):
        rows, summary = self.collect([observation("DevAddr:009356D5")])
        self.assertEqual(rows[0]["name"],"QALCOSONIC W1")
        self.assertFalse(rows[0]["correlated"])
        self.assertEqual(summary["physical_device_count"],0)

    def test_decoder_mtype_and_no_join_accept_decryption(self):
        row={"id":1,"received_at":stamp(NOW),"status":"pending"}
        frames=[bytes(9)+bytes.fromhex(LILY)[::-1]+bytes(6),bytes([0x20])+bytes(16),bytes([0x40])]
        packet=bytes(12)+json.dumps({"rxpk":[{"data":base64.b64encode(frame).decode()} for frame in frames]}).encode()
        decoded=device_decoder.decode_packet(packet,row)
        self.assertEqual([item["mtype"] for item in decoded],[0,1,2])
        self.assertEqual([item["frame_type"] for item in decoded],["JOIN_REQUEST","JOIN_ACCEPT","OTHER"])
        self.assertIsNone(decoded[1]["identity"])
        self.assertNotIn("dev_addr",decoded[1])

    def test_api_cache_publishes_device_summary(self):
        items, registry=three_devices()
        rows, summary=self.collect(items,registry)
        snapshot={"state":"OK","rows":[],"devices":rows,"device_summary":summary}
        with patch.object(web,"poll",new=AsyncMock()),patch.object(queue_monitor,"snapshot",return_value=snapshot):
            with TestClient(web.app) as client:
                web.merge(web.app,web.collect(),"queue")
                self.assertEqual(client.get("/api/devices").json(),rows)
                self.assertEqual(client.get("/api/status").json()["device_summary"],summary)
                with client.websocket_connect("/ws/status") as ws:
                    self.assertEqual(ws.receive_json()["device_summary"]["physical_device_count"],3)
