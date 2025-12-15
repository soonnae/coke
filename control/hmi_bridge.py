"""
HMI Bridge
PLC → REST API
Signed int16 복원 + Ballast 스케일 복원
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
    return v - 0x10000 if v >= 0x8000 else v

class PLCCache:
    def __init__(self, host="localhost", port=502):
        self.client = ModbusTcpClient(host, port=port)
        self.data = {
            "rpm": 0,
            "ballast": 0.0,
            "pump_status": 0,
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

                r = self.client.read_holding_registers(0, 3)
                if not r.isError():
                    with self.lock:
                        self.data["rpm"] = r.registers[0]
                        self.data["ballast"] = r.registers[1] / 10.0
                        self.data["pump_status"] = decode_int16(r.registers[2])
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
