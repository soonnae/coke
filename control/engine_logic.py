"""
⚠️  DEPRECATED - DO NOT USE WITH REAL SENSORS ⚠️

This file generates FAKE/SIMULATED data for testing purposes only.
When using real Field Zone sensors (sensor_sim.py), DO NOT run this file!

Engine Logic Controller
Decision & Physics Layer (SIMULATOR)

This script generates simulated engine data:
- RPM: Fixed pattern (800 → 1000 → 1200 → 900)
- Ballast: Random (40.0 ~ 50.0, ±3.0 change per cycle)
- Pump Mode: Logical decision based on ballast

⚠️  If real sensor data is available, use sensor_to_plc.py instead!
⚠️  Running this will OVERWRITE real sensor data in PLC registers 0-2!

Ballast:
- Range: 40.0 ~ 50.0
- One decimal
- Next value ∈ [prev-3.0, prev+3.0] ∩ [40,50]

Pump Mode (logical):
  +1 = FILL
   0 = HOLD
  -1 = DRAIN

Pump Mode (PLC stored):
  uint16 (encode before write)
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

class EngineLogic:
    def __init__(self, plc_host="localhost", plc_port=502):
        self.client = ModbusTcpClient(plc_host, port=plc_port)
        self.ballast = 45.0
        self.rpm_pattern = [800, 1000, 1200, 900]
        self.rpm_idx = 0

    def connect(self):
        if self.client.connect():
            log.info("[EngineLogic] Connected to PLC")
            return True
        log.error("[EngineLogic] PLC connection failed")
        return False

    def update_ballast(self):
        prev = self.ballast
        low = max(BALLAST_MIN, prev - DELTA_LIMIT)
        high = min(BALLAST_MAX, prev + DELTA_LIMIT)
        self.ballast = round(random.uniform(low, high), 1)

    def decide_pump_mode(self) -> int:
        if self.ballast <= BALLAST_MIN:
            return 1      # FILL
        elif self.ballast >= BALLAST_MAX:
            return -1     # DRAIN
        return 0          # HOLD

    def run(self):
        if not self.connect():
            return

        try:
            while True:
                rpm = self.rpm_pattern[self.rpm_idx]
                self.rpm_idx = (self.rpm_idx + 1) % len(self.rpm_pattern)

                prev_ballast = self.ballast
                self.update_ballast()
                pump_mode = self.decide_pump_mode()

                # 🔑 WRITE (encode signed → uint16)
                self.client.write_register(0, rpm)
                self.client.write_register(1, int(self.ballast * 10))
                self.client.write_register(2, encode_uint16(pump_mode))

                log.info(
                    f"[EngineLogic] RPM={rpm}, "
                    f"Ballast={prev_ballast:.1f}→{self.ballast:.1f}, "
                    f"PumpMode={pump_mode}"
                )

                time.sleep(INTERVAL)

        except KeyboardInterrupt:
            log.info("[EngineLogic] Shutdown")
        finally:
            self.client.close()

if __name__ == "__main__":
    EngineLogic().run()
