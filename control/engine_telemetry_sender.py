"""
Engine Telemetry Sender
Field Zone sensor data → Bridge Zone via UDP
Reads real sensor data from PLC registers 10-21
"""

from pymodbus.client.sync import ModbusTcpClient
import socket
import time
import json
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

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
                # Read Field Zone sensor data from registers 10-21 (12 registers)
                r = self.client.read_holding_registers(10, 12)
                if not r.isError():
                    regs = r.registers
                    data = {
                        "engine": {
                            "rpm": regs[0],
                            "temperature": regs[1],
                            "oil_pressure": regs[2] / 10.0,
                            "load": regs[3]
                        },
                        "fuel": {
                            "level": regs[4],
                            "consumption_rate": regs[5] / 10.0,
                            "temperature": regs[6]
                        },
                        "cooling": {
                            "temperature": regs[7],
                            "pressure": regs[8] / 10.0
                        },
                        "electrical": {
                            "battery_voltage": regs[9] / 10.0
                        },
                        "navigation": {
                            "rudder_angle": regs[10] - 50,  # Remove offset
                            "water_depth": regs[11]
                        },
                        "timestamp": time.time()
                    }

                    self.sock.sendto(
                        json.dumps(data).encode("utf-8"),
                        (self.bridge_ip, self.bridge_port)
                    )

                    log.info(
                        f"[Telemetry] → Bridge: "
                        f"RPM={data['engine']['rpm']}, "
                        f"Temp={data['engine']['temperature']}°C, "
                        f"Oil={data['engine']['oil_pressure']:.1f}bar, "
                        f"Fuel={data['fuel']['level']}%"
                    )

                time.sleep(interval)

        except KeyboardInterrupt:
            pass
        finally:
            self.client.close()
            self.sock.close()

if __name__ == "__main__":
    EngineTelemetrySender().run()
