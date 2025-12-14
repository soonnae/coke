"""
HMI Bridge for Node-RED
Control Zone PLC ↔ Node-RED HMI 연결
HTTP REST API 제공으로 Node-RED에서 PLC 데이터 읽기/쓰기 가능
"""

from pymodbus.client.sync import ModbusTcpClient
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time
import logging
from urllib.parse import urlparse, parse_qs

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class PLCCache:
    """PLC 데이터 캐시 (주기적으로 업데이트)"""
    def __init__(self, plc_host='localhost', plc_port=502):
        self.plc_host = plc_host
        self.plc_port = plc_port
        self.client = None
        self.data = {
            'rpm': 0,
            'ballast': 0,
            'pump_status': 0,
            'pump_coil': False,
            'connected': False,
            'last_update': 0
        }
        self.lock = threading.Lock()

    def connect(self):
        """PLC 연결"""
        try:
            self.client = ModbusTcpClient(self.plc_host, port=self.plc_port)
            if self.client.connect():
                log.info(f"[HMI Bridge] Connected to PLC at {self.plc_host}:{self.plc_port}")
                with self.lock:
                    self.data['connected'] = True
                return True
            else:
                log.error("[HMI Bridge] Failed to connect to PLC")
                return False
        except Exception as e:
            log.error(f"[HMI Bridge] Connection error: {e}")
            return False

    def update_cache(self):
        """캐시 업데이트 (백그라운드 스레드에서 실행)"""
        while True:
            try:
                if not self.data['connected']:
                    if not self.connect():
                        time.sleep(5)
                        continue

                # Holding Registers 읽기
                hr_result = self.client.read_holding_registers(0, 3)
                if not hr_result.isError():
                    with self.lock:
                        self.data['rpm'] = hr_result.registers[0]
                        self.data['ballast'] = hr_result.registers[1]
                        self.data['pump_status'] = hr_result.registers[2]

                # Coil 읽기
                coil_result = self.client.read_coils(0, 1)
                if not coil_result.isError():
                    with self.lock:
                        self.data['pump_coil'] = coil_result.bits[0]
                        self.data['last_update'] = time.time()

                time.sleep(1)  # 1초마다 업데이트

            except Exception as e:
                log.error(f"[HMI Bridge] Update error: {e}")
                with self.lock:
                    self.data['connected'] = False
                time.sleep(5)

    def get_data(self):
        """캐시된 데이터 가져오기"""
        with self.lock:
            return self.data.copy()

    def write_register(self, address, value):
        """레지스터 쓰기"""
        try:
            result = self.client.write_register(address, int(value))
            if not result.isError():
                log.info(f"[HMI Bridge] Write register {address} = {value}")
                return True
            return False
        except Exception as e:
            log.error(f"[HMI Bridge] Write register error: {e}")
            return False

    def write_coil(self, address, value):
        """Coil 쓰기"""
        try:
            result = self.client.write_coil(address, bool(value))
            if not result.isError():
                log.info(f"[HMI Bridge] Write coil {address} = {value}")
                return True
            return False
        except Exception as e:
            log.error(f"[HMI Bridge] Write coil error: {e}")
            return False


class HMIRequestHandler(BaseHTTPRequestHandler):
    """HTTP API 핸들러"""

    def do_GET(self):
        """GET 요청 처리"""
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/api/plc/status':
            # 전체 상태 조회
            data = self.server.plc_cache.get_data()
            self.send_json_response(200, data)

        elif parsed_path.path == '/api/plc/rpm':
            data = self.server.plc_cache.get_data()
            self.send_json_response(200, {'rpm': data['rpm']})

        elif parsed_path.path == '/api/plc/ballast':
            data = self.server.plc_cache.get_data()
            self.send_json_response(200, {'ballast': data['ballast']})

        elif parsed_path.path == '/api/plc/pump':
            data = self.server.plc_cache.get_data()
            self.send_json_response(200, {
                'pump_status': data['pump_status'],
                'pump_coil': data['pump_coil']
            })

        elif parsed_path.path == '/':
            # 간단한 웹 인터페이스
            self.send_html_dashboard()

        else:
            self.send_json_response(404, {'error': 'Not found'})

    def do_POST(self):
        """POST 요청 처리 (PLC 쓰기)"""
        parsed_path = urlparse(self.path)
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data.decode('utf-8'))
        except:
            self.send_json_response(400, {'error': 'Invalid JSON'})
            return

        if parsed_path.path == '/api/plc/write_register':
            # 레지스터 쓰기
            address = data.get('address')
            value = data.get('value')
            if address is not None and value is not None:
                success = self.server.plc_cache.write_register(address, value)
                if success:
                    self.send_json_response(200, {'success': True})
                else:
                    self.send_json_response(500, {'error': 'Write failed'})
            else:
                self.send_json_response(400, {'error': 'Missing address or value'})

        elif parsed_path.path == '/api/plc/write_coil':
            # Coil 쓰기
            address = data.get('address')
            value = data.get('value')
            if address is not None and value is not None:
                success = self.server.plc_cache.write_coil(address, value)
                if success:
                    self.send_json_response(200, {'success': True})
                else:
                    self.send_json_response(500, {'error': 'Write failed'})
            else:
                self.send_json_response(400, {'error': 'Missing address or value'})

        elif parsed_path.path == '/api/plc/pump/toggle':
            # 펌프 토글
            current_state = self.server.plc_cache.get_data()['pump_coil']
            new_state = not current_state
            success = self.server.plc_cache.write_coil(0, new_state)
            if success:
                self.send_json_response(200, {'pump_coil': new_state})
            else:
                self.send_json_response(500, {'error': 'Toggle failed'})

        else:
            self.send_json_response(404, {'error': 'Not found'})

    def send_json_response(self, status_code, data):
        """JSON 응답 전송"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')  # CORS
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_html_dashboard(self):
        """간단한 HTML 대시보드"""
        data = self.server.plc_cache.get_data()
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>PLC HMI Dashboard</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial; margin: 40px; background: #f0f0f0; }}
                .container {{ max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 10px; }}
                h1 {{ color: #333; }}
                .metric {{ background: #e8f4f8; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .metric h3 {{ margin: 0 0 10px 0; color: #0066cc; }}
                .value {{ font-size: 24px; font-weight: bold; }}
                .status {{ display: inline-block; padding: 5px 15px; border-radius: 20px; color: white; }}
                .status.on {{ background: #28a745; }}
                .status.off {{ background: #dc3545; }}
                button {{ padding: 10px 20px; font-size: 16px; cursor: pointer; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚓ Ship Engine Control - HMI Dashboard</h1>

                <div class="metric">
                    <h3>🔧 Engine RPM</h3>
                    <div class="value" id="rpm">{data['rpm']}</div>
                </div>

                <div class="metric">
                    <h3>💧 Ballast Level</h3>
                    <div class="value" id="ballast">{data['ballast']}%</div>
                </div>

                <div class="metric">
                    <h3>⚡ Pump Status</h3>
                    <div class="value">
                        <span class="status {'on' if data['pump_coil'] else 'off'}" id="pump">
                            {'ON' if data['pump_coil'] else 'OFF'}
                        </span>
                    </div>
                    <button onclick="togglePump()">Toggle Pump</button>
                </div>

                <div class="metric">
                    <h3>🔌 Connection Status</h3>
                    <div class="value">
                        <span class="status {'on' if data['connected'] else 'off'}">
                            {'Connected' if data['connected'] else 'Disconnected'}
                        </span>
                    </div>
                </div>
            </div>

            <script>
                // Auto refresh every 2 seconds
                setInterval(() => {{ location.reload(); }}, 2000);

                function togglePump() {{
                    fetch('/api/plc/pump/toggle', {{ method: 'POST' }})
                        .then(response => response.json())
                        .then(data => {{ location.reload(); }});
                }}
            </script>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        """로그 메시지 (너무 많아서 억제)"""
        pass


class HMIBridge:
    def __init__(self, plc_host='localhost', plc_port=502, http_port=8080):
        self.plc_cache = PLCCache(plc_host, plc_port)
        self.http_port = http_port

    def start(self):
        """HMI Bridge 시작"""
        # PLC 캐시 업데이트 스레드 시작
        cache_thread = threading.Thread(target=self.plc_cache.update_cache, daemon=True)
        cache_thread.start()

        # HTTP 서버 시작
        log.info(f"[HMI Bridge] Starting HTTP API server on port {self.http_port}")
        log.info(f"[HMI Bridge] Dashboard: http://localhost:{self.http_port}/")
        log.info(f"[HMI Bridge] API Endpoint: http://localhost:{self.http_port}/api/plc/status")

        server = HTTPServer(('0.0.0.0', self.http_port), HMIRequestHandler)
        server.plc_cache = self.plc_cache

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info("\n[HMI Bridge] Shutting down...")
            server.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='PLC HMI Bridge')
    parser.add_argument('--plc-host', default='localhost', help='PLC server host')
    parser.add_argument('--plc-port', type=int, default=502, help='PLC server port')
    parser.add_argument('--http-port', type=int, default=8080, help='HTTP API port')

    args = parser.parse_args()

    bridge = HMIBridge(
        plc_host=args.plc_host,
        plc_port=args.plc_port,
        http_port=args.http_port
    )

    bridge.start()
