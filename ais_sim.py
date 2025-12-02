"""
AIS (Automatic Identification System) Simulator
선박 자동 식별 시스템 시뮬레이터
"""

import time
import random
import socket
import json
from datetime import datetime

class AISSimulator:
    def __init__(self, host='0.0.0.0', port=10111):
        self.host = host
        self.port = port
        self.socket = None
        
        # 선박 정보
        self.mmsi = 440123456  # Maritime Mobile Service Identity
        self.ship_name = "COKE_VESSEL"
        self.call_sign = "DTAB"
        self.imo = 9876543
        self.ship_type = 70  # Cargo ship
        self.length = 200  # meters
        self.width = 32  # meters
        
        # 위치 정보
        self.latitude = 35.1028
        self.longitude = 129.0403
        self.speed = 10.0  # knots
        self.course = 90.0  # degrees
        self.heading = 90  # degrees
        self.nav_status = 0  # Under way using engine
        
    def start(self):
        """AIS 시뮬레이터 시작"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        print(f"[AIS Simulator] Started on {self.host}:{self.port}")
        
        while True:
            try:
                client, addr = self.socket.accept()
                print(f"[AIS Simulator] Client connected: {addr}")
                self.handle_client(client)
            except KeyboardInterrupt:
                print("\n[AIS Simulator] Shutting down...")
                break
            except Exception as e:
                print(f"[AIS Simulator] Error: {e}")
                
        self.socket.close()
    
    def handle_client(self, client):
        """클라이언트에게 AIS 데이터 전송"""
        try:
            message_count = 0
            while True:
                # AIS 메시지 타입 선택 (Position Report와 Static Data 교대)
                if message_count % 10 == 0:
                    # 10번에 1번은 Static Data (Type 5)
                    ais_data = self.generate_static_data()
                else:
                    # 주로 Position Report (Type 1)
                    ais_data = self.generate_position_report()
                
                # JSON 형식으로 전송
                message = json.dumps(ais_data) + '\n'
                client.send(message.encode('utf-8'))
                
                # 위치 업데이트
                self.update_position()
                
                message_count += 1
                time.sleep(5)  # 5초마다 전송
                
        except (ConnectionResetError, BrokenPipeError):
            print("[AIS Simulator] Client disconnected")
        except Exception as e:
            print(f"[AIS Simulator] Error handling client: {e}")
        finally:
            client.close()
    
    def generate_position_report(self):
        """AIS Type 1 Position Report 생성"""
        return {
            "message_type": 1,
            "mmsi": self.mmsi,
            "timestamp": datetime.utcnow().isoformat(),
            "navigation_status": self.nav_status,
            "rate_of_turn": random.uniform(-5, 5),
            "speed_over_ground": round(self.speed, 1),
            "position_accuracy": 1,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "course_over_ground": round(self.course, 1),
            "true_heading": self.heading,
            "maneuver_indicator": 0,
            "raim_flag": 1
        }
    
    def generate_static_data(self):
        """AIS Type 5 Static and Voyage Related Data 생성"""
        return {
            "message_type": 5,
            "mmsi": self.mmsi,
            "timestamp": datetime.utcnow().isoformat(),
            "imo": self.imo,
            "call_sign": self.call_sign,
            "ship_name": self.ship_name,
            "ship_type": self.ship_type,
            "dimension_to_bow": int(self.length * 0.7),
            "dimension_to_stern": int(self.length * 0.3),
            "dimension_to_port": int(self.width * 0.4),
            "dimension_to_starboard": int(self.width * 0.6),
            "position_fix_type": 1,  # GPS
            "eta": "12-15 14:30",
            "draught": 10.5,
            "destination": "BUSAN PORT"
        }
    
    def update_position(self):
        """선박 위치 업데이트"""
        # 5초 동안 이동
        time_delta = 5
        speed_ms = self.speed * 0.514444  # knots to m/s
        distance = speed_ms * time_delta
        
        import math
        course_rad = math.radians(self.course)
        
        delta_lat = (distance * math.cos(course_rad)) / 111320
        delta_lon = (distance * math.sin(course_rad)) / (111320 * math.cos(math.radians(self.latitude)))
        
        self.latitude += delta_lat
        self.longitude += delta_lon
        
        # 랜덤 변동
        self.latitude += random.uniform(-0.00001, 0.00001)
        self.longitude += random.uniform(-0.00001, 0.00001)
        self.course += random.uniform(-3, 3)
        self.heading = int(self.course + random.uniform(-5, 5))
        self.speed += random.uniform(-0.5, 0.5)
        
        # 범위 제한
        self.speed = max(0, min(25, self.speed))
        self.course = self.course % 360
        self.heading = self.heading % 360

if __name__ == "__main__":
    simulator = AISSimulator(host='0.0.0.0', port=10111)
    simulator.start()
