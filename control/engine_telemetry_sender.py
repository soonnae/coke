"""
Engine Telemetry Sender
Signed int16 복원 포함
"""

from pymodbus.client.sync import ModbusTcpClient
import socket
import time
import json
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def decode_int16(v: int) -> int:
    """uint16 → signed int16"""
    return v - 0x10000 if v >= 0x8000 else v

class EngineTelemetrySender:
    def __init__(self, plc_host="localhost", plc_port=502,
                 bridge_ip="10.10.10.10", bridge_port=10113):
        self.client = ModbusTcpClient(plc_host, port=plc_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.bridge_ip = bridge_ip
        self.bridge_port = bridge_port

    def connect(self):
        return self.client.connect()

    def run(self, interval=2):
        if not self.connect():
            log.error("[Telemetry] PLC connection failed")
            return

        try:
            while True:
                r = self.client.read_holding_registers(0, 3)
                if not r.isError():
                    data = {
                        "rpm": r.registers[0],
                        "ballast": r.registers[1] / 10.0,
                        "pump": decode_int16(r.registers[2]),
                        "timestamp": time.time()
                    }

                    self.sock.sendto(
                        json.dumps(data).encode("utf-8"),
                        (self.bridge_ip, self.bridge_port)
                    )

                    log.info(
                        f"[Telemetry] → Bridge: "
                        f"RPM={data['rpm']}, "
                        f"Ballast={data['ballast']:.1f}, "
                        f"Pump={data['pump']}"
                    )

                time.sleep(interval)

        except KeyboardInterrupt:
            pass
        finally:
            self.client.close()
            self.sock.close()

if __name__ == "__main__":
    EngineTelemetrySender().run()
