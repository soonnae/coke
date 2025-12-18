import time
import random
import socket
import math
from datetime import datetime

TARGET_IP = "10.10.20.10"   # Bridge Zone
TARGET_PORT = 10110

class GPSSimulator:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 초기 위치: 사용자 지정 좌표 (35°06'39.022"N, 129°07'08.2"E)
        self.latitude = 35.11084
        self.longitude = 129.11894
        self.speed = 10.0  # knots
        self.course = 90.0  # 동쪽 (East)
        self.altitude = 0.0

    def start(self):
        print("[GPS Simulator] Sending to:", TARGET_IP, TARGET_PORT)
        print(f"[GPS Simulator] Starting position: {self.latitude:.4f}N, {self.longitude:.4f}E")
        print(f"[GPS Simulator] Course: {self.course}°, Speed: {self.speed} knots")
        while True:
            try:
                # GGA와 RMC 둘 다 전송
                gga = self.generate_gga()
                rmc = self.generate_rmc()

                self.sock.sendto(gga.encode(), (TARGET_IP, TARGET_PORT))
                print(f"[GGA] {gga}")
                time.sleep(0.1)  # 메시지 간 짧은 간격

                self.sock.sendto(rmc.encode(), (TARGET_IP, TARGET_PORT))
                print(f"[RMC] {rmc}")

                self.update_position()
                time.sleep(1)
            except KeyboardInterrupt:
                break

    def generate_gga(self):
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S.00")

        lat_deg = int(abs(self.latitude))
        lat_min = (abs(self.latitude) - lat_deg) * 60
        lat_str = f"{lat_deg:02d}{lat_min:07.4f}"
        lat_dir = 'N' if self.latitude >= 0 else 'S'

        lon_deg = int(abs(self.longitude))
        lon_min = (abs(self.longitude) - lon_deg) * 60
        lon_str = f"{lon_deg:03d}{lon_min:07.4f}"
        lon_dir = 'E' if self.longitude >= 0 else 'W'

        gga = f"GPGGA,{time_str},{lat_str},{lat_dir},{lon_str},{lon_dir},1,10,1.0,{self.altitude},M,0.0,M,,"
        checksum = self.calculate_checksum(gga)
        return f"${gga}*{checksum:02X}"

    def generate_rmc(self):
        """RMC - Recommended Minimum Navigation Information"""
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S.00")
        date_str = now.strftime("%d%m%y")

        lat_deg = int(abs(self.latitude))
        lat_min = (abs(self.latitude) - lat_deg) * 60
        lat_str = f"{lat_deg:02d}{lat_min:07.4f}"
        lat_dir = 'N' if self.latitude >= 0 else 'S'

        lon_deg = int(abs(self.longitude))
        lon_min = (abs(self.longitude) - lon_deg) * 60
        lon_str = f"{lon_deg:03d}{lon_min:07.4f}"
        lon_dir = 'E' if self.longitude >= 0 else 'W'

        # RMC: time,status,lat,NS,lon,EW,speed,course,date,mag_var,EW,mode
        rmc = f"GPRMC,{time_str},A,{lat_str},{lat_dir},{lon_str},{lon_dir},{self.speed:.1f},{self.course:.1f},{date_str},,,"
        checksum = self.calculate_checksum(rmc)
        return f"${rmc}*{checksum:02X}"

    def calculate_checksum(self, sentence):
        """Calculate NMEA checksum"""
        checksum = 0
        for c in sentence:
            checksum ^= ord(c)
        return checksum

    def update_position(self):
        """
        1초마다 위치 업데이트
        - 1 knot = 0.514444 m/s
        - 1도 위도 = 111,320m
        - 1도 경도 = 111,320m * cos(latitude)
        """
        # 1초 동안 이동한 거리 (미터)
        distance_m = self.speed * 0.514444  # knots -> m/s

        # 방향에 따른 위도/경도 변화 계산
        course_rad = math.radians(self.course)

        # 북쪽 방향 이동 (위도 변화)
        delta_lat = (distance_m * math.cos(course_rad)) / 111320.0

        # 동쪽 방향 이동 (경도 변화, 위도에 따라 보정)
        delta_lon = (distance_m * math.sin(course_rad)) / (111320.0 * math.cos(math.radians(self.latitude)))

        self.latitude += delta_lat
        self.longitude += delta_lon

        # 속력 변동 (±0.5 knots)
        self.speed += random.uniform(-0.5, 0.5)
        self.speed = max(5.0, min(15.0, self.speed))

        # 디버깅용 위치 출력
        if int(time.time()) % 10 == 0:  # 10초마다
            print(f"[Position] Lat: {self.latitude:.6f}, Lon: {self.longitude:.6f}, Speed: {self.speed:.1f} knots")

if __name__ == "__main__":
    GPSSimulator().start()
