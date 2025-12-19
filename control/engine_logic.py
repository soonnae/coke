"""
Control Zone Logic - Ballast & Pump Controller
Generates control decisions based on logic

This script controls:
- Ballast: Random simulation (40.0 ~ 50.0, ±3.0 change per cycle)
- Pump Mode: Logical decision based on ballast level

Writes to PLC registers:
- HR[1]: Ballast x10
- HR[2]: Pump Mode (uint16 encoded)

Note: Sensor data (RPM, temperature, etc.) comes from Field Zone via HR[10-21]
"""

from pymodbus.client.sync import ModbusTcpClient
import time
import random
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BALLAST_MIN = 40.0
BALLAST_MAX = 50.0
DELTA_LIMIT = 3.0
INTERVAL = 2

def encode_uint16(v: int) -> int:
    """signed int → uint16 for Modbus write"""
    return v & 0xFFFF

class ControlLogic:
    def __init__(self, plc_host="localhost", plc_port=502):
        self.client = ModbusTcpClient(plc_host, port=plc_port)
        self.ballast = 45.0

    def connect(self):
        if self.client.connect():
            log.info("[ControlLogic] Connected to PLC")
            return True
        log.error("[ControlLogic] PLC connection failed")
        return False

    def update_ballast(self):
        """Update ballast with random walk within constraints"""
        prev = self.ballast
        low = max(BALLAST_MIN, prev - DELTA_LIMIT)
        high = min(BALLAST_MAX, prev + DELTA_LIMIT)
        self.ballast = round(random.uniform(low, high), 1)

    def decide_pump_mode(self) -> int:
        """Decide pump mode based on ballast level"""
        if self.ballast <= BALLAST_MIN:
            return 1      # FILL
        elif self.ballast >= BALLAST_MAX:
            return -1     # DRAIN
        return 0          # HOLD

    def run(self):
        if not self.connect():
            return

        log.info("[ControlLogic] Starting Ballast & Pump control loop")

        try:
            while True:
                prev_ballast = self.ballast
                self.update_ballast()
                pump_mode = self.decide_pump_mode()

                # Write control decisions to PLC
                self.client.write_register(1, int(self.ballast * 10))
                self.client.write_register(2, encode_uint16(pump_mode))

                log.info(
                    f"[ControlLogic] Ballast={prev_ballast:.1f}→{self.ballast:.1f}, "
                    f"PumpMode={pump_mode} "
                    f"({'FILL' if pump_mode == 1 else 'DRAIN' if pump_mode == -1 else 'HOLD'})"
                )

                time.sleep(INTERVAL)

        except KeyboardInterrupt:
            log.info("[ControlLogic] Shutdown")
        finally:
            self.client.close()

if __name__ == "__main__":
    ControlLogic().run()
