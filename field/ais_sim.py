"""
AIS (Automatic Identification System) Simulator
NMEA !AIVDM 출력 + 바다 경계 제한 + GPS 충돌 방지 버전
"""

import time
import random
import socket
import math
from datetime import datetime

# 멀티플렉서가 돌아가는 Field Zone(Raspberry Pi) IP / 포트
TARGET_IP = "10.10.20.10"
TARGET_PORT = 10111   # MUX에서 AIS를 듣는 포트

class AISSimulator:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 기본 선박 정보
        self.mmsi = random.randint(440000000, 440999999)
        self.ship_name = "COKE_VESSEL"
        self.call_sign = "DTAB"
        self.imo = 9876543
        self.ship_type = 70
        self.length = 200
        self.width = 32

        # GPS Ownship(너희 GPS Sim) 위치
        self.GPS_LAT = 35.1028
        self.GPS_LON = 129.0403

        # AIS 시작 위치 → GPS 근처지만 약간 떨어뜨려서 시작
        self.latitude = 35.1128        # GPS보다 북쪽 1km
        self.longitude = 129.0503      # GPS보다 동쪽 1km
        self.speed = 10.0
        self.course = 90.0
        self.heading = 90
        self.nav_status = 0

        # 부산항 바다 경계
        self.LAT_MIN = 35.05
        self.LAT_MAX = 35.20
        self.LON_MIN = 129.00
        self.LON_MAX = 129.20


    # ---------------------------
    # AIS NMEA Utility
    # ---------------------------
    def _sixbit_char(self, val: int) -> str:
        if val < 40:
            return chr(val + 48)
        else:
            return chr(val + 56)

    def _encode_lat_lon(self, lat_deg: float, lon_deg: float):
        lon = max(min(lon_deg, 180.0), -180.0)
        lon_min = lon * 60.0
        lon_1e4_min = int(round(lon_min * 10000))
        if lon_1e4_min < 0:
            lon_1e4_min = (1 << 28) + lon_1e4_min
        lon_raw = lon_1e4_min & ((1 << 28) - 1)

        lat = max(min(lat_deg, 90.0), -90.0)
        lat_min = lat * 60.0
        lat_1e4_min = int(round(lat_min * 10000))
        if lat_1e4_min < 0:
            lat_1e4_min = (1 << 27) + lat_1e4_min
        lat_raw = lat_1e4_min & ((1 << 27) - 1)

        return lat_raw, lon_raw

    def _build_type1_payload(self) -> str:
        sog_raw = int(round(self.speed * 10))
        cog_raw = int(round(self.course * 10)) % 3600
        hdg_raw = int(round(self.heading)) % 360
        rot_raw = 128
        ts_raw = datetime.utcnow().second % 60

        lat_raw, lon_raw = self._encode_lat_lon(self.latitude, self.longitude)

        bits = 0
        length = 0

        def add(value, size):
            nonlocal bits, length
            bits = (bits << size) | (value & ((1 << size) - 1))
            length += size

        # 총 168비트의 Type 1 메시지 구성
        add(1, 6)
        add(0, 2)
        add(self.mmsi, 30)
        add(self.nav_status, 4)
        add(rot_raw, 8)
        add(sog_raw, 10)
        add(1, 1)
        add(lon_raw, 28)
        add(lat_raw, 27)
        add(cog_raw, 12)
        add(hdg_raw, 9)
        add(ts_raw, 6)
        add(0, 2)
        add(0, 3)
        add(0, 1)
        add(0, 19)

        assert length == 168

        sixbits = []
        for i in range(0, length, 6):
            shift = length - 6 - i
            val = (bits >> shift) & 0x3F
            sixbits.append(val)

        payload = "".join(self._sixbit_char(v) for v in sixbits)
        return payload

    def _nmea_checksum(self, body: str) -> str:
        c = 0
        for ch in body:
            c ^= ord(ch)
        return f"{c:02X}"

    def generate_ais_nmea(self) -> str:
        payload = self._build_type1_payload()
        body = f"AIVDM,1,1,,A,{payload},0"
        checksum = self._nmea_checksum(body)
        return f"!{body}*{checksum}"


    # ---------------------------
    # 새로 만든 바다 전용 항해 로직
    # ---------------------------
    def update_position(self):

        # 속도(m/s) 변환
        time_delta = 5.0
        speed_ms = self.speed * 0.514444
        distance = speed_ms * time_delta

        course_rad = math.radians(self.course)
        delta_lat = distance * math.cos(course_rad) / 111320.0
        delta_lon = distance * math.sin(course_rad) / (111320.0 * math.cos(math.radians(self.latitude)))

        new_lat = self.latitude + delta_lat
        new_lon = self.longitude + delta_lon

        # -------------------------
        # 1) 바다 경계 체크 → 벗어나면 즉시 유턴
        # -------------------------
        if not (self.LAT_MIN <= new_lat <= self.LAT_MAX):
            self.course = (self.course + 180) % 360
            return

        if not (self.LON_MIN <= new_lon <= self.LON_MAX):
            self.course = (self.course + 180) % 360
            return

        # 범위 안이면 이동 반영
        self.latitude = new_lat
        self.longitude = new_lon

        # -------------------------
        # 2) GPS Ownship과 충돌 방지
        # -------------------------
        d_lat = (self.latitude - self.GPS_LAT) * 111320.0
        d_lon = (self.longitude - self.GPS_LON) * 88000.0
        distance_m = (d_lat**2 + d_lon**2)**0.5

        if distance_m < 300:  # 300m 이하 접근 시 회피 기동
            self.course = (self.course + 90) % 360

        # -------------------------
        # 3) 자연스러운 항해 움직임
        # -------------------------
        self.course = (self.course + random.uniform(-1.5, 1.5)) % 360
        self.heading = int(self.course + random.uniform(-3, 3))

        self.speed += random.uniform(-0.2, 0.2)
        self.speed = max(5, min(15, self.speed))  # 5~15kn로 제한


    # ---------------------------
    # 실행 루프
    # ---------------------------
    def start(self):
        print(f"[AIS Simulator] Sending AIS to {TARGET_IP}:{TARGET_PORT}")
        print(f"[AIS Simulator] MMSI={self.mmsi}")

        while True:
            try:
                sentence = self.generate_ais_nmea()
                data = (sentence + "\r\n").encode("ascii")
                self.sock.sendto(data, (TARGET_IP, TARGET_PORT))

                print("[SEND AIS]", sentence)

                self.update_position()
                time.sleep(5)

            except KeyboardInterrupt:
                print("\n[AIS Simulator] Shutting down...")
                break
            except Exception as e:
                print(f"[AIS Simulator] Error:", e)


if __name__ == "__main__":
    AISSimulator().start()
