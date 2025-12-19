"""
HMI Bridge
PLC → REST API
Reads Field Zone sensor data and Control Zone control data from PLC
Exposes combined data via REST API
"""

from pymodbus.client.sync import ModbusTcpClient
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def decode_int16(v: int) -> int:
    """uint16 → signed int16"""
    return v - 0x10000 if v >= 0x8000 else v

class PLCCache:
    def __init__(self, host="localhost", port=502):
        self.client = ModbusTcpClient(host, port=port)
        self.data = {
            # Field Zone sensor data (registers 10-21)
            "engine": {
                "rpm": 0,
                "temperature": 0,
                "oil_pressure": 0.0,
                "load": 0
            },
            "fuel": {
                "level": 0,
                "consumption_rate": 0.0,
                "temperature": 0
            },
            "cooling": {
                "temperature": 0,
                "pressure": 0.0
            },
            "electrical": {
                "battery_voltage": 0.0
            },
            "navigation": {
                "rudder_angle": 0,
                "water_depth": 0
            },
            # Control Zone control data (registers 1-2)
            "control": {
                "ballast": 0.0,
                "pump_mode": 0
            },
            "connected": False,
            "last_update": 0
        }
        self.lock = threading.Lock()

    def connect(self):
        if self.client.connect():
            self.data["connected"] = True
            return True
        return False

    def update(self):
        while True:
            try:
                if not self.data["connected"]:
                    if not self.connect():
                        time.sleep(3)
                        continue

                # Read control data registers (1-2)
                r_control = self.client.read_holding_registers(1, 2)

                # Read sensor data registers (10-21, total 12 registers)
                r_sensors = self.client.read_holding_registers(10, 12)

                if not r_control.isError() and not r_sensors.isError():
                    with self.lock:
                        # Control Zone control data
                        self.data["control"]["ballast"] = r_control.registers[0] / 10.0
                        self.data["control"]["pump_mode"] = decode_int16(r_control.registers[1])

                        # Field Zone sensor data
                        regs = r_sensors.registers
                        self.data["engine"]["rpm"] = regs[0]
                        self.data["engine"]["temperature"] = regs[1]
                        self.data["engine"]["oil_pressure"] = regs[2] / 10.0
                        self.data["engine"]["load"] = regs[3]

                        self.data["fuel"]["level"] = regs[4]
                        self.data["fuel"]["consumption_rate"] = regs[5] / 10.0
                        self.data["fuel"]["temperature"] = regs[6]

                        self.data["cooling"]["temperature"] = regs[7]
                        self.data["cooling"]["pressure"] = regs[8] / 10.0

                        self.data["electrical"]["battery_voltage"] = regs[9] / 10.0

                        self.data["navigation"]["rudder_angle"] = regs[10] - 50  # Remove offset
                        self.data["navigation"]["water_depth"] = regs[11]

                        self.data["last_update"] = time.time()

                time.sleep(1)

            except Exception:
                self.data["connected"] = False
                time.sleep(3)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/plc/status":
            self.send_json(200, self.server.cache.data)
        else:
            self.send_json(404, {"error": "not found"})

    def send_json(self, code, payload):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, *_):
        pass

class HMIBridge:
    def __init__(self, http_port=8080):
        self.cache = PLCCache()
        self.http_port = http_port

    def start(self):
        t = threading.Thread(target=self.cache.update, daemon=True)
        t.start()

        server = HTTPServer(("0.0.0.0", self.http_port), Handler)
        server.cache = self.cache

        log.info(f"[HMI Bridge] API http://localhost:{self.http_port}/api/plc/status")
        server.serve_forever()

if __name__ == "__main__":
    HMIBridge().start()
