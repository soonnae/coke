"""
GPS Simulator for Ship Navigation System
선박 항법 시스템용 GPS 시뮬레이터
"""

import time
import random
import socket
import math
from datetime import datetime

class GPSSimulator:
    def __init__(self, host='0.0.0.0', port=10110):
        self.host = host
        self.port = port
        self.socket = None
        
        # 초기 위치 (부산항 인근)
        self.latitude = 35.1028
        self.longitude = 129.0403
        self.speed = 10.0  # knots
        self.course = 90.0  # degrees
        self.altitude = 0.0
        
    def start(self):
        """GPS 시뮬레이터 시작"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        print(f"[GPS Simulator] Started on {self.host}:{self.port}")
        
        while True:
            try:
                client, addr = self.socket.accept()
                print(f"[GPS Simulator] Client connected: {addr}")
                self.handle_client(client)
            except KeyboardInterrupt:
                print("\n[GPS Simulator] Shutting down...")
                break
            except Exception as e:
                print(f"[GPS Simulator] Error: {e}")
                
        self.socket.close()
    
    def handle_client(self, client):
        """클라이언트에게 GPS 데이터 전송"""
        try:
            while True:
                # GPS 데이터 생성
                nmea_sentence = self.generate_gps_data()
                
                # 클라이언트에 전송
                client.send((nmea_sentence + '\r\n').encode('utf-8'))
                
                # 위치 업데이트
                self.update_position()
                
                time.sleep(1)  # 1초마다 전송
                
        except (ConnectionResetError, BrokenPipeError):
            print("[GPS Simulator] Client disconnected")
        except Exception as e:
            print(f"[GPS Simulator] Error handling client: {e}")
        finally:
            client.close()
    
    def generate_gps_data(self):
        """NMEA 형식의 GPS 데이터 생성 (GGA 문장)"""
        now = datetime.utcnow()
        
        # 시간 포맷 (HHMMSS)
        time_str = now.strftime("%H%M%S")
        
        # 위도 변환 (DDMM.MMMM)
        lat_deg = int(abs(self.latitude))
        lat_min = (abs(self.latitude) - lat_deg) * 60
        lat_str = f"{lat_deg:02d}{lat_min:07.4f}"
        lat_dir = 'N' if self.latitude >= 0 else 'S'
        
        # 경도 변환 (DDDMM.MMMM)
        lon_deg = int(abs(self.longitude))
        lon_min = (abs(self.longitude) - lon_deg) * 60
        lon_str = f"{lon_deg:03d}{lon_min:07.4f}"
        lon_dir = 'E' if self.longitude >= 0 else 'W'
        
        # GPS 품질 (1=GPS fix)
        quality = "1"
        
        # 위성 수
        num_satellites = random.randint(8, 12)
        
        # HDOP (수평 정밀도)
        hdop = f"{random.uniform(0.8, 1.2):.1f}"
        
        # 고도
        altitude = f"{self.altitude:.1f}"
        
        # NMEA GGA 문장 생성
        gga_data = f"GPGGA,{time_str},{lat_str},{lat_dir},{lon_str},{lon_dir},{quality},{num_satellites},{hdop},{altitude},M,0.0,M,,"
        
        # 체크섬 계산
        checksum = self.calculate_checksum(gga_data)
        
        return f"${gga_data}*{checksum:02X}"
    
    def calculate_checksum(self, sentence):
        """NMEA 체크섬 계산"""
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)
        return checksum
    
    def update_position(self):
        """선박 위치 업데이트"""
        # 속도를 미터/초로 변환 (1 knot = 0.514444 m/s)
        speed_ms = self.speed * 0.514444
        
        # 1초 동안 이동한 거리
        distance = speed_ms  # meters
        
        # 위도/경도 변화 계산
        # 1도 위도 ≈ 111,320 미터
        # 1도 경도 ≈ 111,320 * cos(위도) 미터
        
        course_rad = math.radians(self.course)
        
        delta_lat = (distance * math.cos(course_rad)) / 111320
        delta_lon = (distance * math.sin(course_rad)) / (111320 * math.cos(math.radians(self.latitude)))
        
        self.latitude += delta_lat
        self.longitude += delta_lon
        
        # 약간의 랜덤 변동 추가 (현실감)
        self.latitude += random.uniform(-0.00001, 0.00001)
        self.longitude += random.uniform(-0.00001, 0.00001)
        self.course += random.uniform(-2, 2)
        self.speed += random.uniform(-0.5, 0.5)
        
        # 범위 제한
        self.speed = max(0, min(25, self.speed))
        self.course = self.course % 360

if __name__ == "__main__":
    simulator = GPSSimulator(host='0.0.0.0', port=10110)
    simulator.start()
