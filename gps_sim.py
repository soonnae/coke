import time
import random
import socket
import math
from datetime import datetime

TARGET_IP = "192.168.0.165"   # RouterOS WAN IP
TARGET_PORT = 10110

class GPSSimulator:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 초기 위치
        self.latitude = 35.1028
        self.longitude = 129.0403
        self.speed = 10.0
        self.course = 90.0
        self.altitude = 0.0

    def start(self):
        print("[GPS Simulator] Sending to:", TARGET_IP, TARGET_PORT)
        while True:
            try:
                nmea = self.generate_gga()
                self.sock.sendto(nmea.encode(), (TARGET_IP, TARGET_PORT))
                print("[SEND]", nmea)
                self.update_position()
                time.sleep(1)
            except KeyboardInterrupt:
                break

    def generate_gga(self):
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S")

        lat_deg = int(abs(self.latitude))
        lat_min = (abs(self.latitude) - lat_deg) * 60
        lat_str = f"{lat_deg:02d}{lat_min:07.4f}"
        lat_dir = 'N' if self.latitude >= 0 else 'S'

        lon_deg = int(abs(self.longitude))
        lon_min = (abs(self.longitude) - lon_deg) * 60
        lon_str = f"{lon_deg:03d}{lon_min:07.4f}"
        lon_dir = 'E' if self.longitude >= 0 else 'W'

        gga = f"GPGGA,{time_str},{lat_str},{lat_dir},{lon_str},{lon_dir},1,10,1.0,{self.altitude},M,0.0,M,,"
        checksum = 0
        for c in gga:
            checksum ^= ord(c)
        return f"${gga}*{checksum:02X}"

    def update_position(self):
        speed_ms = self.speed * 0.514444
        distance = speed_ms

        course_rad = math.radians(self.course)
        delta_lat = distance * math.cos(course_rad) / 111320
        delta_lon = distance * math.sin(course_rad) / (111320 * math.cos(math.radians(self.latitude)))

        self.latitude += delta_lat
        self.longitude += delta_lon

if __name__ == "__main__":
    GPSSimulator().start()
