"""Pruebas aisladas: SQLite temporal y UDP simulado; sin importar el proxy."""
import hashlib
import json
import queue
import socket
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from test_stat_forwarding import FUNCTIONS, SOURCE, ReceiverSocket, environment, packet


class FastPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ns = environment()
        self.ns.update(threading=threading, sqlite3=sqlite3, hashlib=hashlib, datetime=datetime,
                       timezone=timezone, Path=Path, time=time, socket=socket,
                       db_lock=threading.Lock(), push_lock=threading.Lock(),
                       in_flight=set(), fast_queue=queue.Queue(),
                       DB_PATH=str(Path(self.tmp.name) / "queue.db"),
                       ACK_TIMEOUT=0.05, QUEUE_BATCH_SIZE=10, IDLE_INTERVAL=5)
        exec(compile(FUNCTIONS, str(SOURCE), "exec"), self.ns)
        self.ns["init_db"]()
        self.data = packet(0, {"rxpk": [
            {"tmst": 2023419325, "time": "2020-01-01T00:00:00Z", "data": "AA=="},
            {"tmst": 2023419326, "time": "2020-01-01T00:00:01Z", "data": "AQ=="}]})
        self.info = self.ns["parse_semtech_packet"](self.data)

    def row(self):
        with sqlite3.connect(self.ns["DB_PATH"]) as conn:
            return conn.execute("SELECT status, attempts, sent_at, ack_at, "
                                "delay_seconds, raw_packet, original_time "
                                "FROM uplink_queue").fetchone()

    def run_fast(self, ack):
        transport = Mock()
        transport.__enter__ = Mock(return_value=transport)
        transport.__exit__ = Mock(return_value=False)
        self.ns["socket"] = Mock(AF_INET=socket.AF_INET, SOCK_DGRAM=socket.SOCK_DGRAM)
        self.ns["socket"].socket.return_value = transport

        def send(data, **kwargs):
            self.assertEqual(data, self.data)
            self.assertEqual(self.row()[:2], ("pending", 1))
            self.assertFalse(self.ns["claim_packet"](1))
            self.ns["running"] = False
            if isinstance(ack, Exception):
                raise ack
            return ack

        self.ns["send_push_and_wait_ack"] = Mock(side_effect=send)
        self.ns["fast_worker"]()
        self.assertEqual(self.ns["in_flight"], set())
        self.assertEqual(self.ns["fast_queue"].unfinished_tasks, 0)

    def test_persist_reserve_deduplicate_and_ack(self):
        self.ns["save_packet"](self.data, self.info, fast_path=True)
        self.assertEqual(self.row()[0], "pending")
        self.assertFalse(self.ns["claim_packet"](1))
        self.assertEqual(self.ns["save_packet"](self.data, self.info, fast_path=True),
                         (None, False, None))
        self.assertEqual(self.ns["fast_queue"].qsize(), 1)
        original = self.row()[6]
        self.run_fast(True)
        row = self.row()
        self.assertEqual(row[:2], ("sent", 1))
        self.assertTrue(row[2] and row[3])
        self.assertGreaterEqual(row[4], 0)
        self.assertEqual(row[5:], (self.data, original))
        self.assertFalse(self.ns["claim_packet"](1))  # Snapshot viejo no reenvia.

    def test_timeout_releases_for_retry_without_losing_data(self):
        self.ns["save_packet"](self.data, self.info, fast_path=True)
        self.run_fast(False)
        self.assertEqual(self.row()[:5], ("pending", 1, None, None, None))
        self.assertTrue(self.ns["claim_packet"](1))
        self.assertFalse(self.ns["claim_packet"](1))

    def test_exception_releases_reservation(self):
        self.ns["save_packet"](self.data, self.info, fast_path=True)
        self.run_fast(OSError("network unavailable"))
        self.assertEqual(self.row()[:2], ("pending", 1))
        self.assertTrue(self.ns["claim_packet"](1))

    def test_restart_retry_injects_original_time_preserving_tmst_and_storage(self):
        self.ns["save_packet"](self.data, self.info, fast_path=True)
        original = self.row()[6]
        self.ns["in_flight"].clear()  # Memoria de proceso nuevo.
        self.ns["fast_queue"] = queue.Queue()
        def send(data):
            self.assertEqual(data[:12], self.data[:12])
            actual = json.loads(data[12:])
            expected = json.loads(self.data[12:])
            for rxpk in expected["rxpk"]:
                rxpk["time"] = self.ns["epoch_to_iso_z"](original)
            self.assertEqual(actual, expected)
            self.ns["running"] = False
            return True
        self.ns["send_push_and_wait_ack"] = send
        self.ns["time"] = Mock(time=time.time)
        self.ns["queue_worker"]()
        self.assertEqual(self.row()[:2], ("sent", 1))
        self.assertEqual(self.row()[5:], (self.data, original))

    def test_receiver_forwards_control_without_waiting_for_fast_ack(self):
        self.ns["send_push_and_wait_ack"] = Mock()
        self.ns["local_socket"] = ReceiverSocket(self.ns, [self.data, packet(2), packet(5)])
        self.ns["down_socket"] = Mock()
        self.ns["local_receiver"]()
        self.assertEqual(self.row()[:2], ("pending", 0))
        self.assertEqual(self.ns["fast_queue"].qsize(), 1)
        self.assertEqual(self.ns["down_socket"].sendto.call_count, 2)
        self.ns["send_push_and_wait_ack"].assert_not_called()

    def test_full_fast_queue_keeps_durable_pending_for_worker(self):
        self.ns["fast_queue"] = queue.Queue(maxsize=1)
        self.ns["fast_queue"].put_nowait((999, b"busy"))
        self.ns["save_packet"](self.data, self.info, fast_path=True)
        self.assertEqual(self.row()[:2], ("pending", 0))
        self.assertTrue(self.ns["claim_packet"](1))
        self.assertEqual(self.row()[5], self.data)

    def test_control_continues_during_active_fast_ack_wait(self):
        self.ns["save_packet"](self.data, self.info, fast_path=True)
        entered, release = threading.Event(), threading.Event()
        def send(data, **kwargs):
            entered.set()
            release.wait(2)
            return False
        self.ns["send_push_and_wait_ack"] = send
        transport = Mock()
        transport.__enter__ = Mock(return_value=transport)
        transport.__exit__ = Mock(return_value=False)
        self.ns["socket"] = Mock()
        self.ns["socket"].socket.return_value = transport
        self.ns["local_socket"] = ReceiverSocket(self.ns, [packet(2), packet(5)])
        self.ns["down_socket"] = Mock()
        worker = threading.Thread(target=self.ns["fast_worker"], daemon=True)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            self.ns["local_receiver"]()
            self.assertFalse(release.is_set())
            self.assertEqual(self.ns["down_socket"].sendto.call_count, 2)
            self.assertFalse(self.ns["claim_packet"](1))
        finally:
            self.ns["running"] = False
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())

    def test_queue_worker_skips_reserved_packet(self):
        self.ns["save_packet"](self.data, self.info, fast_path=True)
        self.ns["send_push_and_wait_ack"] = Mock()
        def stop_on_sleep(seconds):
            self.ns["running"] = False
        self.ns["time"] = Mock(sleep=stop_on_sleep)
        self.ns["queue_worker"]()
        self.ns["send_push_and_wait_ack"].assert_not_called()
        self.assertEqual(self.row()[:2], ("pending", 0))
        self.assertIn(1, self.ns["in_flight"])

    def run_fast_with_real_ack_parser(self, responses):
        self.ns["save_packet"](self.data, self.info, fast_path=True)
        transport = Mock()
        transport.__enter__ = Mock(return_value=transport)
        transport.__exit__ = Mock(return_value=False)
        def receive(size):
            self.ns["running"] = False
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response, ("127.0.0.1", 1700)
        transport.recvfrom.side_effect = receive
        original_mark_sent = self.ns["mark_sent"]
        self.ns["mark_sent"] = Mock(side_effect=original_mark_sent)
        with patch.object(socket, "socket", return_value=transport):
            self.ns["fast_worker"]()
        transport.send.assert_called_once_with(self.data)
        transport.settimeout.assert_called_once_with(self.ns["ACK_TIMEOUT"])
        self.assertEqual(self.ns["in_flight"], set())
        return self.ns["mark_sent"]

    def test_fast_worker_marks_sent_only_after_valid_push_ack(self):
        mark_sent = self.run_fast_with_real_ack_parser([
            b"\x02\x00\x00\x01", self.data[:3] + b"\x04",
            self.data[:3] + b"\x01"])
        mark_sent.assert_called_once_with(1)
        self.assertEqual(self.row()[:2], ("sent", 1))

    def test_fast_worker_socket_timeout_never_marks_sent(self):
        mark_sent = self.run_fast_with_real_ack_parser([
            b"\x02\x00\x00\x01", socket.timeout("no valid ACK")])
        mark_sent.assert_not_called()
        self.assertEqual(self.row()[:5], ("pending", 1, None, None, None))

    def test_dedicated_ack_validates_token_and_bypasses_backlog_lock(self):
        transport = Mock()
        transport.recvfrom.side_effect = [
            (b"\x02\x00\x00\x01", ("127.0.0.1", 1700)),
            (self.data[:3] + b"\x04", ("127.0.0.1", 1700)),
            (self.data[:3] + b"\x01", ("127.0.0.1", 1700))]
        self.ns["push_lock"].acquire()
        result = []
        worker = threading.Thread(target=lambda: result.append(
            self.ns["send_push_and_wait_ack"](self.data, transport=transport)), daemon=True)
        try:
            worker.start()
            worker.join(1)
            self.assertFalse(worker.is_alive(), "Fast-path espera lock de backlog")
            self.assertEqual(result, [True])
            transport.send.assert_called_once_with(self.data)
        finally:
            self.ns["push_lock"].release()
            worker.join(1)


if __name__ == "__main__":
    unittest.main()
