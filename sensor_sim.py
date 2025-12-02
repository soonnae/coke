"""
Ship Sensor Simulator
선박 센서 시뮬레이터 (엔진, 연료, 온도 등)
"""

import time
import random
import socket
import json
from datetime import datetime

class SensorSimulator:
    def __init__(self, host='0.0.0.0', port=10112):
        self.host = host
        self.port = port
        self.socket = None
        
        # 엔진 센서 (메인 엔진)
        self.engine_rpm = 850.0
        self.engine_temp = 85.0  # Celsius
        self.engine_oil_pressure = 4.5  # bar
        self.engine_load = 60.0  # percentage
        
        # 연료 시스템
        self.fuel_level = 75.0  # percentage
        self.fuel_consumption = 12.5  # L/hour
        self.fuel_temp = 35.0  # Celsius
        
        # 냉각 시스템
        self.coolant_temp = 82.0  # Celsius
        self.coolant_pressure = 1.8  # bar
        
        # 기타 센서
        self.battery_voltage = 24.5  # V
        self.rudder_angle = 0.0  # degrees
        self.water_depth = 50.0  # meters
        
        # 알람 상태
        self.alarms = []
        
    def start(self):
        """센서 시뮬레이터 시작"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        print(f"[Sensor Simulator] Started on {self.host}:{self.port}")
        
        while True:
            try:
                client, addr = self.socket.accept()
                print(f"[Sensor Simulator] Client connected: {addr}")
                self.handle_client(client)
            except KeyboardInterrupt:
                print("\n[Sensor Simulator] Shutting down...")
                break
            except Exception as e:
                print(f"[Sensor Simulator] Error: {e}")
                
        self.socket.close()
    
    def handle_client(self, client):
        """클라이언트에게 센서 데이터 전송"""
        try:
            while True:
                # 센서 데이터 생성
                sensor_data = self.generate_sensor_data()
                
                # JSON 형식으로 전송
                message = json.dumps(sensor_data, indent=2) + '\n'
                client.send(message.encode('utf-8'))
                
                # 센서 값 업데이트
                self.update_sensors()
                
                time.sleep(2)  # 2초마다 전송
                
        except (ConnectionResetError, BrokenPipeError):
            print("[Sensor Simulator] Client disconnected")
        except Exception as e:
            print(f"[Sensor Simulator] Error handling client: {e}")
        finally:
            client.close()
    
    def generate_sensor_data(self):
        """센서 데이터 생성"""
        # 알람 체크
        self.check_alarms()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "engine": {
                "rpm": round(self.engine_rpm, 1),
                "temperature": round(self.engine_temp, 1),
                "oil_pressure": round(self.engine_oil_pressure, 2),
                "load": round(self.engine_load, 1)
            },
            "fuel": {
                "level": round(self.fuel_level, 1),
                "consumption_rate": round(self.fuel_consumption, 2),
                "temperature": round(self.fuel_temp, 1)
            },
            "cooling": {
                "temperature": round(self.coolant_temp, 1),
                "pressure": round(self.coolant_pressure, 2)
            },
            "electrical": {
                "battery_voltage": round(self.battery_voltage, 2)
            },
            "navigation": {
                "rudder_angle": round(self.rudder_angle, 1),
                "water_depth": round(self.water_depth, 1)
            },
            "alarms": self.alarms.copy()
        }
    
    def update_sensors(self):
        """센서 값 업데이트"""
        # 엔진 RPM (±50)
        self.engine_rpm += random.uniform(-50, 50)
        self.engine_rpm = max(600, min(1200, self.engine_rpm))
        
        # 엔진 온도 (±2도)
        self.engine_temp += random.uniform(-2, 2)
        self.engine_temp = max(75, min(105, self.engine_temp))
        
        # 엔진 오일 압력 (±0.3 bar)
        self.engine_oil_pressure += random.uniform(-0.3, 0.3)
        self.engine_oil_pressure = max(3.0, min(6.0, self.engine_oil_pressure))
        
        # 엔진 부하 (±5%)
        self.engine_load += random.uniform(-5, 5)
        self.engine_load = max(30, min(95, self.engine_load))
        
        # 연료 레벨 (서서히 감소)
        self.fuel_level -= self.fuel_consumption / 1000  # 점진적 감소
        self.fuel_level = max(10, min(100, self.fuel_level))
        
        # 연료 소비율 (±1 L/h)
        self.fuel_consumption += random.uniform(-1, 1)
        self.fuel_consumption = max(8, min(20, self.fuel_consumption))
        
        # 냉각수 온도 (±1.5도)
        self.coolant_temp += random.uniform(-1.5, 1.5)
        self.coolant_temp = max(70, min(95, self.coolant_temp))
        
        # 냉각수 압력 (±0.2 bar)
        self.coolant_pressure += random.uniform(-0.2, 0.2)
        self.coolant_pressure = max(1.0, min(2.5, self.coolant_pressure))
        
        # 배터리 전압 (±0.5V)
        self.battery_voltage += random.uniform(-0.5, 0.5)
        self.battery_voltage = max(22.0, min(28.0, self.battery_voltage))
        
        # 키 각도 (±10도)
        self.rudder_angle += random.uniform(-10, 10)
        self.rudder_angle = max(-35, min(35, self.rudder_angle))
        
        # 수심 (±5m)
        self.water_depth += random.uniform(-5, 5)
        self.water_depth = max(10, min(200, self.water_depth))
    
    def check_alarms(self):
        """알람 상태 체크"""
        self.alarms = []
        
        # 엔진 온도 경고
        if self.engine_temp > 100:
            self.alarms.append({
                "level": "WARNING",
                "code": "ENG_TEMP_HIGH",
                "message": f"Engine temperature high: {self.engine_temp:.1f}°C"
            })
        
        # 오일 압력 경고
        if self.engine_oil_pressure < 3.5:
            self.alarms.append({
                "level": "WARNING",
                "code": "OIL_PRESS_LOW",
                "message": f"Engine oil pressure low: {self.engine_oil_pressure:.2f} bar"
            })
        
        # 연료 레벨 경고
        if self.fuel_level < 20:
            self.alarms.append({
                "level": "CAUTION",
                "code": "FUEL_LEVEL_LOW",
                "message": f"Fuel level low: {self.fuel_level:.1f}%"
            })
        
        # 배터리 전압 경고
        if self.battery_voltage < 23.0:
            self.alarms.append({
                "level": "CAUTION",
                "code": "BATTERY_LOW",
                "message": f"Battery voltage low: {self.battery_voltage:.2f}V"
            })
        
        # 수심 경고
        if self.water_depth < 15:
            self.alarms.append({
                "level": "WARNING",
                "code": "SHALLOW_WATER",
                "message": f"Shallow water: {self.water_depth:.1f}m"
            })

if __name__ == "__main__":
    simulator = SensorSimulator(host='0.0.0.0', port=10112)
    simulator.start()
