"""
AIS (Automatic Identification System) Simulator
선박 자동 식별 시스템 시뮬레이터 - NMEA !AIVDM 출력 버전
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

        # 선박 정보
        self.mmsi = random.randint(440000000, 440999999)  # 한국 MMSI 대역 랜덤
        self.ship_name = "COKE_VESSEL"
        self.call_sign = "DTAB"
        self.imo = 9876543
        self.ship_type = 70   # Cargo ship
        self.length = 200     # meters
        self.width = 32       # meters

        # 위치 정보 (GPS랑 비슷한 해역으로 설정)
        self.latitude = 35.1028
        self.longitude = 129.0403
        self.speed = 10.0     # knots
        self.course = 90.0    # degrees
        self.heading = 90     # degrees
        self.nav_status = 0   # Under way using engine

    # ---------------------------
    # AIS 6-bit / NMEA 유틸 함수
    # ---------------------------

    def _sixbit_char(self, val: int) -> str:
        """6-bit 값을 AIS 문자로 변환"""
        if val < 40:
            return chr(val + 48)
        else:
            return chr(val + 56)

    def _encode_lat_lon(self, lat_deg: float, lon_deg: float):
        """
        AIS 포맷(1/10000분 단위, 2의 보수)으로 위경도 인코딩
        lat: 27bit, lon: 28bit
        """
        # 경도: -180 ~ 180
        lon = max(min(lon_deg, 180.0), -180.0)
        lon_min = lon * 60.0
        lon_1e4_min = int(round(lon_min * 10000))

        if lon_1e4_min < 0:
            lon_1e4_min = (1 << 28) + lon_1e4_min
        lon_raw = lon_1e4_min & ((1 << 28) - 1)

        # 위도: -90 ~ 90
        lat = max(min(lat_deg, 90.0), -90.0)
        lat_min = lat * 60.0
        lat_1e4_min = int(round(lat_min * 10000))

        if lat_1e4_min < 0:
            lat_1e4_min = (1 << 27) + lat_1e4_min
        lat_raw = lat_1e4_min & ((1 << 27) - 1)

        return lat_raw, lon_raw

    def _build_type1_payload(self) -> str:
        """
        AIS Type 1 Position Report → 6-bit 페이로드 문자열 생성
        (문자열 부분만, !AIVDM 앞뒤 래핑은 따로)
        """
        # SOG (0.1 knots, 10bit)
        sog = max(0.0, min(self.speed, 102.2))
        sog_raw = int(round(sog * 10))

        # COG (0.1°, 12bit)
        cog = self.course % 360.0
        cog_raw = int(round(cog * 10)) % 3600

        # Heading (정수°, 9bit)
        hdg = int(round(self.heading)) % 360
        hdg_raw = hdg

        # ROT: 여기선 사용 안 해서 128 (not available)
        rot_raw = 128

        # Timestamp: UTC 초 단위
        ts_raw = datetime.utcnow().second % 60

        # Lat/Lon 인코딩
        lat_raw, lon_raw = self._encode_lat_lon(self.latitude, self.longitude)

        bits = 0
        length = 0

        def add(value, size):
            nonlocal bits, length
            bits = (bits << size) | (value & ((1 << size) - 1))
            length += size

        # 필드 순서/크기 (총 168bit)
        add(1, 6)                      # Message Type = 1
        add(0, 2)                      # Repeat Indicator
        add(self.mmsi, 30)             # MMSI
        add(self.nav_status, 4)        # Navigation Status
        add(rot_raw, 8)                # Rate of Turn
        add(sog_raw, 10)               # Speed Over Ground
        add(1, 1)                      # Position Accuracy
        add(lon_raw, 28)               # Longitude
        add(lat_raw, 27)               # Latitude
        add(cog_raw, 12)               # Course Over Ground
        add(hdg_raw, 9)                # True Heading
        add(ts_raw, 6)                 # Timestamp
        add(0, 2)                      # Maneuver Indicator
        add(0, 3)                      # Spare
        add(0, 1)                      # RAIM flag
        add(0, 19)                     # Communication state (간단히 0)

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
        """
        최종 NMEA !AIVDM 문장 생성
        예: !AIVDM,1,1,,A,<payload>,0*CS
        """
        payload = self._build_type1_payload()
        # single-fragment AIVDM
        body = f"AIVDM,1,1,,A,{payload},0"
        checksum = self._nmea_checksum(body)
        sentence = f"!{body}*{checksum}"
        return sentence

    # ---------------------------
    # 위치 업데이트 / 메인 루프
    # ---------------------------

    def update_position(self):
        """선박 위치 업데이트 (5초 간 이동량 기준)"""
        time_delta = 5.0
        speed_ms = self.speed * 0.514444  # knots → m/s
        distance = speed_ms * time_delta

        course_rad = math.radians(self.course)

        delta_lat = distance * math.cos(course_rad) / 111320.0
        delta_lon = distance * math.sin(course_rad) / (
            111320.0 * math.cos(math.radians(self.latitude))
        )

        self.latitude += delta_lat
        self.longitude += delta_lon

        # 약간 랜덤 흔들림
        self.latitude += random.uniform(-0.00001, 0.00001)
        self.longitude += random.uniform(-0.00001, 0.00001)
        self.course += random.uniform(-2, 2)
        self.heading = int(self.course + random.uniform(-5, 5))
        self.speed += random.uniform(-0.5, 0.5)

        # 범위 제한
        self.speed = max(0, min(25, self.speed))
        self.course = self.course % 360
        self.heading = self.heading % 360

    def start(self):
        print(f"[AIS Simulator] Sending AIS NMEA to {TARGET_IP}:{TARGET_PORT}")
        print(f"[AIS Simulator] MMSI={self.mmsi}")
        while True:
            try:
                sentence = self.generate_ais_nmea()
                # NMEA는 CRLF로 끝나는 한 줄
                data = (sentence + "\r\n").encode("ascii")
                self.sock.sendto(data, (TARGET_IP, TARGET_PORT))
                print("[SEND AIS]", sentence)

                self.update_position()
                time.sleep(5)

            except KeyboardInterrupt:
                print("\n[AIS Simulator] Shutting down...")
                break
            except Exception as e:
                print(f"[AIS Simulator] Error: {e}")

if __name__ == "__main__":
    AISSimulator().start()
