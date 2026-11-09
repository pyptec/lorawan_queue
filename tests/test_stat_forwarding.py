"""Exercise receiver functions without importing the module or opening sockets."""
import ast
import json
from pathlib import Path
import queue
import threading
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "lorawan_queue.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))
FUNCTIONS = ast.Module(
    body=[node for node in TREE.body if isinstance(node, ast.FunctionDef)],
    type_ignores=[],
)


def environment():
    ns = dict(queue=queue, json=json, running=True, last_pull_client=None,
              LOCAL_IP="127.0.0.1", LOCAL_PORT=1700, TTN_HOST="ttn.invalid",
              TTN_PORT=1700, PUSH_DATA=0, PUSH_ACK=1, PULL_DATA=2,
              PULL_RESP=3, PULL_ACK=4, TX_ACK=5,
              client_lock=threading.Lock(), stat_queue=queue.Queue(maxsize=100),
              print=Mock(), save_packet=Mock(return_value=(1, True, 123)))
    exec(compile(FUNCTIONS, str(SOURCE), "exec"), ns)
    # Replace persistence after loading functions; SQLite must never run here.
    ns["save_packet"] = Mock(return_value=(1, True, 123))
    return ns


def packet(kind, payload=None):
    header = bytes([2, 0x12, 0x34, kind]) + bytes(8)
    return header + (json.dumps(payload).encode() if payload is not None else b"")


class ReceiverSocket:
    def __init__(self, ns, packets, before_second=None):
        self.ns, self.packets = ns, iter(packets)
        self.count, self.before_second = 0, before_second
        self.sendto = Mock()

    def recvfrom(self, size):
        if self.count == 1 and self.before_second:
            self.before_second()
        self.count += 1
        try:
            return next(self.packets), ("127.0.0.1", 12345)
        except StopIteration:
            self.ns["running"] = False
            return b"", ("127.0.0.1", 12345)


class StatForwardingTests(unittest.TestCase):
    def test_receiver_continues_while_remote_ack_is_blocked(self):
        ns = environment()
        entered, release, received = threading.Event(), threading.Event(), threading.Event()

        def blocked_send(data):
            entered.set()
            release.wait(3)
            return False

        ns["send_push_and_wait_ack"] = blocked_send
        stat, pull, tx = packet(0, {"stat": {}}), packet(2), packet(5)

        def wait_for_sender():
            if not entered.wait(2):
                raise RuntimeError("Stats sender did not start")

        ns["local_socket"] = ReceiverSocket(ns, [stat, pull, tx], wait_for_sender)
        ns["down_socket"] = Mock()
        worker = threading.Thread(target=ns["stat_worker"], daemon=True)
        receiver = threading.Thread(target=lambda: (ns["local_receiver"](), received.set()), daemon=True)
        worker.start()
        receiver.start()
        try:
            self.assertTrue(received.wait(2), "Receiver waited for remote ACK")
            self.assertFalse(release.is_set())
            self.assertEqual(ns["down_socket"].sendto.call_args_list,
                             [unittest.mock.call(pull, ("ttn.invalid", 1700)),
                              unittest.mock.call(tx, ("ttn.invalid", 1700))])
            ns["local_socket"].sendto.assert_called_once_with(stat[:3] + b"\x01", ("127.0.0.1", 12345))
            ns["save_packet"].assert_not_called()
        finally:
            ns["running"] = False
            release.set()
            worker.join(4)
            receiver.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(ns["stat_queue"].unfinished_tasks, 0)

    def test_full_queue_drops_stats_and_still_forwards_control(self):
        ns = environment()
        for _ in range(100):
            ns["stat_queue"].put_nowait(b"old")
        ns["send_push_and_wait_ack"] = Mock()
        stat, pull, tx = packet(0, {"stat": {}}), packet(2), packet(5)
        ns["local_socket"] = ReceiverSocket(ns, [stat, pull, tx])
        ns["down_socket"] = Mock()
        ns["local_receiver"]()
        ns["print"].assert_any_call("[WARN] stat_queue llena")
        ns["send_push_and_wait_ack"].assert_not_called()
        self.assertEqual(ns["stat_queue"].qsize(), 100)
        self.assertEqual(ns["down_socket"].sendto.call_count, 2)
        ns["local_socket"].sendto.assert_called_once_with(stat[:3] + b"\x01", ("127.0.0.1", 12345))

    def test_worker_completes_queue_task_on_ack_timeout_and_exception(self):
        for result in (True, False, RuntimeError("send failed")):
            with self.subTest(result=result):
                ns = environment()
                data = packet(0, {"stat": {}})
                ns["stat_queue"].put_nowait(data)

                def send(value):
                    self.assertEqual(value, data)
                    ns["running"] = False
                    if isinstance(result, Exception):
                        raise result
                    return result

                ns["send_push_and_wait_ack"] = send
                ns["stat_worker"]()
                self.assertEqual(ns["stat_queue"].unfinished_tasks, 0)
                self.assertTrue(ns["stat_queue"].empty())

    def test_mixed_rxpk_stat_keeps_persistence_before_local_ack(self):
        ns = environment()
        data = packet(0, {"rxpk": [{"data": "AA=="}], "stat": {}})
        ns["local_socket"] = ReceiverSocket(ns, [data])
        ns["send_push_and_wait_ack"] = Mock()
        ns["save_packet"].side_effect = lambda *args: (
            self.assertEqual(ns["local_socket"].sendto.call_count, 0) or (1, True, 123))
        ns["local_receiver"]()
        ns["save_packet"].assert_called_once()
        ns["local_socket"].sendto.assert_called_once()
        self.assertTrue(ns["stat_queue"].empty())
        ns["send_push_and_wait_ack"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
