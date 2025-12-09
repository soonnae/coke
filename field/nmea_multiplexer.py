"""
NMEA Multiplexer
GPS/AIS NMEA 문장을 받아 Bridge(OpenCPN)로 그대로 포워딩
Sensor 데이터는 NAV 시스템에 불필요하므로 Forward하지 않음.
"""

import socket
import threading
import time

# 🔧 Bridge(OpenCPN) VM으로 전달할 목적지 IP/Port
TARGET_IP = "10.10.10.10"      # Bridge Zone (OpenCPN)
TARGET_PORT = 10110            # OpenCPN이 듣는 NMEA 포트

# 🔧 Field Zone 수신 포트
GPS_PORT = 10110
AIS_PORT = 10111
SENSOR_PORT = 10112            # Sensor는 NAV로 전달하지 않음

class NMEAMultiplexer:
    def __init__(self):
        # 수신 소켓
        self.gps_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ais_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sensor_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 송신 소켓
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 포트 바인딩
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
        print(f"[GPS   ] 0.0.0.0:{GPS_PORT}")
        print(f"[AIS   ] 0.0.0.0:{AIS_PORT}")
        print(f"[Sensor] 0.0.0.0:{SENSOR_PORT}")
        print(f"[FORWARD] → {TARGET_IP}:{TARGET_PORT}")

        # Thread 시작
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
    # GPS 처리
    # ------------------------------
    def receive_gps(self):
        print("[NMEA MUX] GPS receiver started")
        while self.running:
            try:
                data, addr = self.gps_sock.recvfrom(4096)
                if not data:
                    continue

                msg = data.decode("ascii", errors="ignore").strip()
                print(f"[GPS] {msg}")

                self.stats["gps_received"] += 1

                # GPS는 사람이 판독하기 쉽게 strip했지만 CRLF 붙여서 포워딩
                send_data = (msg + "\r\n").encode("ascii")
                self.send_sock.sendto(send_data, (TARGET_IP, TARGET_PORT))
                self.stats["messages_sent"] += 1

            except Exception as e:
                print("[GPS ERROR]", e)

    # ------------------------------
    # AIS 처리 (절대! 가공 안 됨)
    # ------------------------------
    def receive_ais(self):
        print("[NMEA MUX] AIS receiver started")
        while self.running:
            try:
                data, addr = self.ais_sock.recvfrom(4096)
                if not data:
                    continue

                # 로그 출력은 decode해서 하고
                print("[AIS]", data.decode("ascii", errors="ignore").strip())

                self.stats["ais_received"] += 1

                # 🟦 핵심: AIS 문장은 절대 가공하지 않고 RAW 그대로 포워딩
                # CRLF 없는 경우만 붙여줌
                if not data.endswith(b"\n"):
                    data = data + b"\r\n"

                self.send_sock.sendto(data, (TARGET_IP, TARGET_PORT))
                self.stats["messages_sent"] += 1

            except Exception as e:
                print("[AIS ERROR]", e)

    # ------------------------------
    # SENSOR 처리 (포워딩 안 함)
    # ------------------------------
    def receive_sensor(self):
        print("[NMEA MUX] Sensor receiver started")
        while self.running:
            try:
                data, addr = self.sensor_sock.recvfrom(4096)
                msg = data.decode("utf-8", errors="ignore").strip()
                print(f"[SENSOR] {msg}")
                self.stats["sensor_received"] += 1

            except Exception as e:
                print("[SENSOR ERROR]", e)

    # ------------------------------
    # 통계 출력
    # ------------------------------
    def print_stats(self):
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
