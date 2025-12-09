"""
NMEA Multiplexer
GPS / AIS NMEA 데이터를 받아서 Bridge(OpenCPN)로 순수 포워딩
Sensor 데이터는 NAV 시스템에 불필요하므로 Forward하지 않음.
"""

import socket
import threading
import time

# 🔧 Bridge(OpenCPN) VM으로 전달할 목적지 IP/Port
TARGET_IP = "10.10.10.10"     # 기존 너 코드 그대로
TARGET_PORT = 10110           # OpenCPN이 듣는 포트

# 🔧 Field Zone에서 들어오는 Raw 데이터 포트
GPS_PORT = 10110
AIS_PORT = 10111
SENSOR_PORT = 10112           # Sensor는 Forward 안 함

class NMEAMultiplexer:
    def __init__(self):
        # 수신 소켓
        self.gps_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ais_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sensor_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 송신 소켓
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 바인딩
        self.gps_sock.bind(("0.0.0.0", GPS_PORT))
        self.ais_sock.bind(("0.0.0.0", AIS_PORT))
        self.sensor_sock.bind(("0.0.0.0", SENSOR_PORT))

        self.stats = {
            "gps_received": 0,
            "ais_received": 0,
            "sensor_received": 0,
            "messages_sent": 0
        }

        self.running = True

    def start(self):
        print("[NMEA MUX] Starting listeners...")
        print(f"[GPS   ] Listening on 0.0.0.0:{GPS_PORT}")
        print(f"[AIS   ] Listening on 0.0.0.0:{AIS_PORT}")
        print(f"[Sensor] Listening on 0.0.0.0:{SENSOR_PORT}")
        print(f"[FORWARD] → {TARGET_IP}:{TARGET_PORT}")

        # 스레드 시작
        threading.Thread(target=self.receive_gps, daemon=True).start()
        threading.Thread(target=self.receive_ais, daemon=True).start()
        threading.Thread(target=self.receive_sensor, daemon=True).start()
        threading.Thread(target=self.print_stats, daemon=True).start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[NMEA MUX] Shutting down...")
            self.running = False

    # ------------------------------
    # RECEIVE + FORWARD FUNCTIONS
    # ------------------------------

    def forward_raw(self, data: bytes, source: str):
        """순수 NMEA 문장을 그대로 브릿지로 포워딩"""
        try:
            # 원본 그대로 보냄 (절대 가공 금지)
            self.send_sock.sendto(data, (TARGET_IP, TARGET_PORT))
            self.stats["messages_sent"] += 1
            msg_preview = data.decode(errors='ignore').strip()
            print(f"[FORWARD {source}] {msg_preview}")
        except Exception as e:
            print(f"[ERROR {source}] Forward error: {e}")

    def receive_gps(self):
        print("[NMEA MUX] GPS receiver started")
        while self.running:
            try:
                data, addr = self.gps_sock.recvfrom(4096)
                msg = data.decode("ascii", errors="ignore").strip()
                if msg:
                    print(f"[GPS] {msg}")
                    self.stats["gps_received"] += 1
                    # CRLF 붙여서 포워딩 → OpenCPN이 정확히 인식함
                    self.forward_raw((msg + "\r\n").encode("ascii"), "GPS")
            except Exception as e:
                print(f"[GPS ERROR] {e}")

    def receive_ais(self):
        print("[NMEA MUX] AIS receiver started")
        while self.running:
            try:
                data, addr = self.ais_sock.recvfrom(4096)
                msg = data.decode("ascii", errors="ignore").strip()
                if msg:
                    print(f"[AIS] {msg}")
                    self.stats["ais_received"] += 1
                    self.forward_raw((msg + "\r\n").encode("ascii"), "AIS")
            except Exception as e:
                print(f"[AIS ERROR] {e}")

    def receive_sensor(self):
        print("[NMEA MUX] Sensor receiver started")
        while self.running:
            try:
                data, addr = self.sensor_sock.recvfrom(4096)
                msg = data.decode("utf-8", errors="ignore").strip()

                # Sensor는 NAV 시스템에 필요 없음 → Forward 안 함
                print(f"[SENSOR] {msg}")   # 로그만 표시
                self.stats["sensor_received"] += 1

            except Exception as e:
                print(f"[SENSOR ERROR] {e}")

    def print_stats(self):
        """30초마다 통계 출력"""
        while self.running:
            time.sleep(30)
            print("\n[NMEA MUX] ===== Statistics =====")
            print(f" GPS Received:    {self.stats['gps_received']}")
            print(f" AIS Received:    {self.stats['ais_received']}")
            print(f" Sensor Received: {self.stats['sensor_received']}")
            print(f" Messages Sent:   {self.stats['messages_sent']}")
            print("=================================\n")


if __name__ == "__main__":
    NMEAMultiplexer().start()
