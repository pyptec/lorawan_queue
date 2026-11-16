import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from dashboard import ups_monitor as ups, app as web


def words(*values):
    return [byte for value in values for byte in (value & 255, value >> 8)]


class UPSTests(unittest.TestCase):
    def bus(self, flags=0, current=0xFFF8, percent=72, cells=(3808, 3805, 3838, 3797), vbus=10):
        bus = Mock(spec=["read_byte_data", "read_i2c_block_data", "close"])
        bus.read_byte_data.return_value = flags
        blocks = {0x10: words(vbus, 8, 0), 0x20: words(15248, current, percent, 3438, 22920, 65535), 0x30: words(*cells)}
        bus.read_i2c_block_data.side_effect = lambda address, register, size: blocks[register]
        return bus

    def read(self, bus):
        return ups.UPSMonitor(lambda number: bus).read()

    def test_charge_states_and_read_only_registers(self):
        for flags, expected in ((0, "IDLE"), (0x80, "CHARGING"), (0x40, "FAST_CHARGING"), (0x20, "DISCHARGING")):
            with self.subTest(flags=flags):
                bus = self.bus(flags)
                self.assertEqual(self.read(bus)["charge_state"], expected)
                bus.read_byte_data.assert_called_once_with(0x2D, 0x02)
                self.assertEqual([c.args for c in bus.read_i2c_block_data.call_args_list], [(0x2D, 0x10, 6), (0x2D, 0x20, 12), (0x2D, 0x30, 8)])
                bus.close.assert_called_once()

    def test_charge_flag_priority_including_observed_a2(self):
        # 0xA2 supplied as real hardware evidence; bus readings here are mocks.
        for flags, expected in ((0x00, "IDLE"), (0x20, "DISCHARGING"),
                                (0x40, "FAST_CHARGING"), (0x80, "CHARGING"),
                                (0xA0, "CHARGING"), (0xC0, "FAST_CHARGING"),
                                (0xE0, "FAST_CHARGING"), (0xA2, "CHARGING")):
            with self.subTest(flags=hex(flags)):
                result = self.read(self.bus(flags=flags))
                self.assertEqual(result["state"], "OK")
                self.assertEqual(result["charge_state"], expected)
                self.assertIsNone(result["error"])

    def test_signed_fff8_and_positive_boundaries(self):
        for raw, expected in ((0xFFF8, -8), (8, 8), (0x8000, -32768), (0x7FFF, 32767), (0, 0), (0xFFFF, -1)):
            with self.subTest(raw=raw):
                result = self.read(self.bus(current=raw))
                self.assertEqual(result["battery_current_ma"], expected)
                self.assertEqual(result["battery_power_mw"], round(15248 * abs(expected) / 1000, 2))
                self.assertEqual(result["battery_power_source"], "CALCULADA")

    def test_percent_thresholds(self):
        for percent, state in ((0, "CRITICAL"), (9, "CRITICAL"), (10, "LOW"), (19, "LOW"), (20, "WARNING"), (49, "WARNING"), (50, "OK"), (100, "OK")):
            self.assertEqual(self.read(self.bus(percent=percent))["battery_state"], state)

    def test_cells_and_raw_times(self):
        result = self.read(self.bus())
        self.assertEqual(result["cells_mv"], [3808, 3805, 3838, 3797])
        self.assertEqual((result["cell_min_mv"], result["cell_max_mv"], result["cell_delta_mv"]), (3797, 3838, 41))
        self.assertEqual(result["runtime_to_empty_min"], 22920)
        self.assertIsNone(result["time_to_full_min"])
        for delta, state in ((49, "OK"), (50, "WARNING"), (100, "WARNING"), (101, "ATTENTION")):
            self.assertEqual(self.read(self.bus(cells=(3800, 3800 + delta, 3800, 3800)))["cell_balance_state"], state)

    def test_external_power_noise_and_uncertainty(self):
        for mv, expected in ((8, False), (10, False), (1000, False), (1001, None), (3999, None), (4000, True), (12000, True)):
            self.assertIs(self.read(self.bus(vbus=mv))["external_power"], expected)

    def test_absent_and_io_errors(self):
        for error in (FileNotFoundError, OSError, IOError, TimeoutError, ImportError):
            result = ups.UPSMonitor(Mock(side_effect=error)).read()
            self.assertEqual(result["state"], "UNKNOWN")
            self.assertNotIn("battery_percent", result)
        bus = self.bus()
        bus.read_i2c_block_data.side_effect = OSError
        self.assertEqual(self.read(bus)["state"], "UNKNOWN")
        bus.close.assert_called_once()

    def test_short_and_invalid_reads(self):
        for block in ([], [0], [0] * 5, [0] * 7, [0, 0, 0, 0, 0, 256], [0, 0, 0, 0, 0, -1]):
            bus = self.bus()
            bus.read_i2c_block_data.side_effect = None
            bus.read_i2c_block_data.return_value = block
            self.assertEqual(self.read(bus)["state"], "UNKNOWN")
        for bus in (self.bus(percent=101), self.bus(cells=(0, 3800, 3800, 3800)), self.bus(flags=256), self.bus(vbus=65535)):
            self.assertEqual(self.read(bus)["state"], "UNKNOWN")

    def test_sampler_timeout_reaps_child(self):
        context = Mock()
        receive, send, process = Mock(), Mock(), Mock()
        context.Pipe.return_value = (receive, send)
        context.Process.return_value = process
        receive.poll.return_value = False
        process.is_alive.side_effect = [True, False, False]
        with patch.object(ups.multiprocessing, "get_context", return_value=context):
            self.assertEqual(ups.snapshot()["state"], "UNKNOWN")
        receive.poll.assert_called_once_with(ups.READ_TIMEOUT)
        process.terminate.assert_called_once()
        process.close.assert_called_once()
        receive.close.assert_called_once()

    def test_api_and_ws_cached_unknown_and_ok_without_i2c(self):
        with patch.object(web, "poll", new=AsyncMock()), patch.object(ups, "snapshot") as read:
            with TestClient(web.app) as client:
                for sample in (ups.unknown(), self.read(self.bus())):
                    web.app.state.snapshot = {"ups": sample, "queue": {"state": "UNKNOWN"}}
                    self.assertEqual(client.get("/api/ups").status_code, 200)
                    self.assertEqual(client.get("/api/ups").json(), sample)
                    with client.websocket_connect("/ws/status") as ws:
                        self.assertEqual(ws.receive_json()["ups"], sample)
                self.assertEqual(client.post("/api/ups").status_code, 405)
                read.assert_not_called()


class UPSIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_ups_does_not_delay_other_sources(self):
        import threading
        release = threading.Event()
        app = SimpleNamespace(state=SimpleNamespace(snapshot={}))
        def slow():
            release.wait(2)
            return ups.unknown()
        tasks = [asyncio.create_task(web.poll(app, slow, "ups", 60)), asyncio.create_task(web.poll(app, lambda: {"state": "OK"}, "system", 60))]
        try:
            for _ in range(100):
                if "system" in app.state.snapshot:
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(app.state.snapshot["system"]["state"], "OK")
            self.assertNotIn("ups", app.state.snapshot)
        finally:
            release.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
