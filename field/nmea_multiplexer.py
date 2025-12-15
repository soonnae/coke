"""
NMEA Multiplexer
GPS/AIS NMEA 문장을 받아 Bridge(OpenCPN)로 그대로 포워딩
Sensor 데이터는 JSON으로 받아:
  1) Control Zone (sensor_to_plc.py)로 JSON 포워딩
  2) Bridge Zone (OpenCPN)로 NMEA XDR 변환 후 포워딩
"""

import socket
import threading
import time
import json

# 🔧 Bridge(OpenCPN) VM으로 전달할 목적지 IP/Port
TARGET_IP = "10.10.10.10"      # Bridge Zone (OpenCPN)
TARGET_PORT = 10110            # OpenCPN이 듣는 NMEA 포트

# 🔧 Control Zone 목적지 (Sensor 데이터 JSON 포워딩)
CONTROL_IP = "10.10.20.10"     # Control Zone (PLC Server)
CONTROL_PORT = 10112           # sensor_to_plc.py가 듣는 포트

# 🔧 Field Zone 수신 포트
GPS_PORT = 10110
AIS_PORT = 10111
SENSOR_PORT = 10112            # Sensor 데이터 수신 후 양쪽으로 전달

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

    def nmea_checksum(self, sentence):
        """NMEA 체크섬 계산 ($ 제외, * 제외)"""
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)
        return f"{checksum:02X}"

    def json_to_nmea_xdr(self, json_str):
        """
        센서 JSON 데이터를 NMEA XDR (Transducer) 문장들로 변환
        여러 개의 XDR 문장을 생성하여 리스트로 반환

        XDR 형식: $<talker>XDR,<type>,<value>,<unit>,<name>,...*<checksum>
        type: C=온도, P=압력, V=전압, A=각도, G=일반, etc.
        """
        try:
            data = json.loads(json_str)
            xdr_sentences = []

            # 엔진 센서 데이터
            if 'engine' in data:
                eng = data['engine']
                # 엔진 RPM, 온도, 오일 압력, 부하를 하나의 XDR에
                fields = []
                if 'rpm' in eng:
                    fields.extend(['G', str(eng['rpm']), 'R', 'EngineRPM'])
                if 'temperature' in eng:
                    fields.extend(['C', str(eng['temperature']), 'C', 'EngineTemp'])
                if 'oil_pressure' in eng:
                    fields.extend(['P', str(eng['oil_pressure']), 'B', 'OilPress'])
                if 'load' in eng:
                    fields.extend(['G', str(eng['load']), 'P', 'EngineLoad'])

                if fields:
                    body = 'GPXDR,' + ','.join(fields)
                    checksum = self.nmea_checksum(body)
                    xdr_sentences.append(f"${body}*{checksum}")

            # 연료 시스템
            if 'fuel' in data:
                fuel = data['fuel']
                fields = []
                if 'level' in fuel:
                    fields.extend(['G', str(fuel['level']), 'P', 'FuelLevel'])
                if 'consumption_rate' in fuel:
                    fields.extend(['G', str(fuel['consumption_rate']), 'L', 'FuelFlow'])
                if 'temperature' in fuel:
                    fields.extend(['C', str(fuel['temperature']), 'C', 'FuelTemp'])

                if fields:
                    body = 'GPXDR,' + ','.join(fields)
                    checksum = self.nmea_checksum(body)
                    xdr_sentences.append(f"${body}*{checksum}")

            # 냉각 시스템
            if 'cooling' in data:
                cool = data['cooling']
                fields = []
                if 'temperature' in cool:
                    fields.extend(['C', str(cool['temperature']), 'C', 'CoolantTemp'])
                if 'pressure' in cool:
                    fields.extend(['P', str(cool['pressure']), 'B', 'CoolantPress'])

                if fields:
                    body = 'GPXDR,' + ','.join(fields)
                    checksum = self.nmea_checksum(body)
                    xdr_sentences.append(f"${body}*{checksum}")

            # 전기 시스템
            if 'electrical' in data:
                elec = data['electrical']
                fields = []
                if 'battery_voltage' in elec:
                    fields.extend(['V', str(elec['battery_voltage']), 'V', 'Battery'])

                if fields:
                    body = 'GPXDR,' + ','.join(fields)
                    checksum = self.nmea_checksum(body)
                    xdr_sentences.append(f"${body}*{checksum}")

            # 항해 시스템
            if 'navigation' in data:
                nav = data['navigation']
                fields = []
                if 'rudder_angle' in nav:
                    fields.extend(['A', str(nav['rudder_angle']), 'D', 'Rudder'])
                if 'water_depth' in nav:
                    fields.extend(['G', str(nav['water_depth']), 'M', 'Depth'])

                if fields:
                    body = 'GPXDR,' + ','.join(fields)
                    checksum = self.nmea_checksum(body)
                    xdr_sentences.append(f"${body}*{checksum}")

            return xdr_sentences

        except json.JSONDecodeError as e:
            print(f"[MUX] JSON decode error: {e}")
            return []
        except Exception as e:
            print(f"[MUX] XDR conversion error: {e}")
            return []

    def start(self):
        print("[NMEA MUX] Starting listeners...")
        print(f"[GPS   ] 0.0.0.0:{GPS_PORT}")
        print(f"[AIS   ] 0.0.0.0:{AIS_PORT}")
        print(f"[Sensor] 0.0.0.0:{SENSOR_PORT}")
        print(f"[FORWARD GPS/AIS] → Bridge Zone: {TARGET_IP}:{TARGET_PORT}")
        print(f"[FORWARD SENSOR JSON] → Control Zone: {CONTROL_IP}:{CONTROL_PORT}")
        print(f"[FORWARD SENSOR NMEA] → Bridge Zone: {TARGET_IP}:{TARGET_PORT}")

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
    # SENSOR 처리 (Control & Bridge 양쪽으로 포워딩)
    # ------------------------------
    def receive_sensor(self):
        print("[NMEA MUX] Sensor receiver started")
        print(f"[NMEA MUX] Sensor JSON → Control Zone: {CONTROL_IP}:{CONTROL_PORT}")
        print(f"[NMEA MUX] Sensor NMEA → Bridge Zone: {TARGET_IP}:{TARGET_PORT}")
        while self.running:
            try:
                data, addr = self.sensor_sock.recvfrom(4096)
                msg = data.decode("utf-8", errors="ignore").strip()
                print(f"[SENSOR] Received: {msg[:80]}...")  # 처음 80자만 출력
                self.stats["sensor_received"] += 1

                # 1️⃣ Control Zone으로 JSON 그대로 포워딩
                self.send_sock.sendto(data, (CONTROL_IP, CONTROL_PORT))
                print(f"[SENSOR→Control] JSON forwarded to {CONTROL_IP}:{CONTROL_PORT}")

                # 2️⃣ Bridge Zone으로 NMEA XDR 변환 후 포워딩
                xdr_sentences = self.json_to_nmea_xdr(msg)
                for xdr in xdr_sentences:
                    xdr_data = (xdr + "\r\n").encode("ascii")
                    self.send_sock.sendto(xdr_data, (TARGET_IP, TARGET_PORT))
                    print(f"[SENSOR→Bridge] {xdr}")
                    self.stats["messages_sent"] += 1

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
