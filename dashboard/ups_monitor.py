"""Telemetría UPS HAT E: solo lecturas SMBus, sin dependencia de LoRaWAN."""
import multiprocessing
import time

SOURCE = "I2C 0x2d"
READ_TIMEOUT = 2.0


def unknown(error="UPS no disponible"):
    return {"state": "UNKNOWN", "source": SOURCE, "charge_state": "UNKNOWN",
            "battery_state": "UNKNOWN", "sampled_at": time.time(), "error": error}


class UPSMonitor:
    ADDRESS = 0x2D

    def __init__(self, bus_factory=None):
        self.bus_factory = bus_factory

    def read(self):
        bus = None
        try:
            factory = self.bus_factory
            if factory is None:
                from smbus2 import SMBus
                factory = SMBus
            bus = factory(1)
            flags = bus.read_byte_data(self.ADDRESS, 0x02)
            if type(flags) is not int or not 0 <= flags <= 255:
                raise ValueError("Invalid status")
            def block(register, length):
                data = bus.read_i2c_block_data(self.ADDRESS, register, length)
                if len(data) != length or any(type(b) is not int or not 0 <= b <= 255 for b in data):
                    raise ValueError("Invalid block")
                return [data[i] | (data[i + 1] << 8) for i in range(0, length, 2)]
            vbus = block(0x10, 6)
            battery = block(0x20, 12)
            cells = block(0x30, 8)
            voltage, raw_current, percent, capacity, runtime, full = battery
            # Plausibility filters, not manufacturer alarm specifications.
            if not 0 < voltage < 65535 or not 0 <= percent <= 100 or any(not 0 < c < 65535 for c in cells):
                raise ValueError("Invalid measurement")
            if any(v == 65535 for v in vbus) or capacity == 65535:
                raise ValueError("Invalid measurement")
            current = raw_current - 0x10000 if raw_current >= 0x8000 else raw_current
            # Priority from the original script; recognized bits can coexist (0xA2).
            if flags & 0x40:
                charge = "FAST_CHARGING"
            elif flags & 0x80:
                charge = "CHARGING"
            elif flags & 0x20:
                charge = "DISCHARGING"
            else:
                charge = "IDLE"
            external = True if vbus[0] >= 4000 else False if vbus[0] <= 1000 else None
            delta = max(cells) - min(cells)
            return {"state": "OK", "source": SOURCE, "charge_state": charge,
                    "battery_state": "OK" if percent >= 50 else "WARNING" if percent >= 20 else "LOW" if percent >= 10 else "CRITICAL",
                    "battery_percent": percent, "battery_voltage_mv": voltage,
                    "battery_current_ma": current, "battery_power_mw": round(voltage * abs(current) / 1000, 2),
                    "battery_power_source": "CALCULADA", "remaining_capacity_mah": capacity,
                    "runtime_to_empty_min": None if runtime == 65535 else runtime,
                    "time_to_full_min": None if full == 65535 else full,
                    "vbus_voltage_mv": vbus[0], "vbus_current_ma": vbus[1], "vbus_power_mw": vbus[2],
                    "external_power": external,
                    "external_power_state": "PRESENT" if external is True else "NOT_PRESENT" if external is False else "UNKNOWN",
                    "cells_mv": cells, "cell_min_mv": min(cells), "cell_max_mv": max(cells),
                    "cell_delta_mv": delta, "cell_balance_state": "OK" if delta < 50 else "WARNING" if delta <= 100 else "ATTENTION",
                    "sampled_at": time.time(), "error": None}
        except Exception as exc:
            # Fixed error text: no arbitrary device/library details exposed to HTTP.
            return unknown("I2C read failed (" + type(exc).__name__ + ")")
        finally:
            if bus is not None:
                try:
                    bus.close()
                except Exception:
                    pass


def _read_child(connection):
    try:
        connection.send(UPSMonitor().read())
    finally:
        connection.close()


def snapshot():
    """A fresh spawned process bounds stuck driver calls; no accumulating threads."""
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_read_child, args=(send,), daemon=True)
    started = False
    try:
        process.start()
        started = True
        send.close()
        if not receive.poll(READ_TIMEOUT):
            return unknown("I2C read timeout")
        return receive.recv()
    except Exception as exc:
        return unknown("I2C sampler failed (" + type(exc).__name__ + ")")
    finally:
        send.close()
        receive.close()
        if started:
            process.join(0.1)
            if process.is_alive():
                process.terminate()
                process.join(0.1)
            if process.is_alive():
                process.kill()
                process.join(0.1)
            if not process.is_alive():
                process.close()
