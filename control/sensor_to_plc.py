"""
Sensor to PLC Connector
Field Zone Sensor Simulator 데이터를 Control Zone PLC로 연결
UDP로 JSON 센서 데이터를 수신하여 Modbus 레지스터에 매핑
"""

from pymodbus.client import ModbusTcpClient
import socket
import json
import logging
import time

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class SensorToPLC:
    def __init__(self,
                 sensor_port=10112,
                 plc_host='localhost',
                 plc_port=502):
        """
        Args:
            sensor_port: Sensor Simulator로부터 데이터를 수신할 포트
            plc_host: PLC 서버 주소
            plc_port: PLC 서버 포트
        """
        self.sensor_port = sensor_port
        self.plc_host = plc_host
        self.plc_port = plc_port

        # UDP 수신 소켓
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.sensor_port))

        # Modbus 클라이언트
        self.plc_client = None

        # PLC 레지스터 매핑 (확장 가능하도록 높은 주소 사용)
        # 기존: 0=RPM, 1=Ballast, 2=Pump (engine_logic.py 사용)
        # 추가: 10~20번 레지스터에 센서 데이터 매핑
        self.register_map = {
            'engine_rpm': 10,           # 엔진 RPM
            'engine_temp': 11,          # 엔진 온도
            'oil_pressure': 12,         # 오일 압력 (x10)
            'engine_load': 13,          # 엔진 부하 (%)
            'fuel_level': 14,           # 연료 레벨 (%)
            'fuel_consumption': 15,     # 연료 소비율 (x10)
            'fuel_temp': 16,            # 연료 온도
            'coolant_temp': 17,         # 냉각수 온도
            'coolant_pressure': 18,     # 냉각수 압력 (x10)
            'battery_voltage': 19,      # 배터리 전압 (x10)
            'rudder_angle': 20,         # 키 각도 (+ offset 50)
            'water_depth': 21,          # 수심
        }

        # 통계
        self.stats = {
            'received': 0,
            'parsed': 0,
            'written': 0,
            'errors': 0
        }

    def connect_plc(self):
        """PLC에 연결"""
        try:
            self.plc_client = ModbusTcpClient(self.plc_host, port=self.plc_port)
            if self.plc_client.connect():
                log.info(f"[Sensor→PLC] Connected to PLC at {self.plc_host}:{self.plc_port}")
                return True
            else:
                log.error("[Sensor→PLC] Failed to connect to PLC")
                return False
        except Exception as e:
            log.error(f"[Sensor→PLC] Connection error: {e}")
            return False

    def parse_sensor_json(self, message):
        """
        JSON 센서 메시지 파싱
        형식:
        {
          "engine": {"rpm": 850, "temperature": 85, "oil_pressure": 4.5, "load": 60},
          "fuel": {"level": 75, "consumption_rate": 12.5, "temperature": 35},
          "cooling": {"temperature": 82, "pressure": 1.8},
          "electrical": {"battery_voltage": 24.5},
          "navigation": {"rudder_angle": 0, "water_depth": 50}
        }
        """
        try:
            data_dict = {}
            sensor_data = json.loads(message)

            # Engine 데이터
            if 'engine' in sensor_data:
                eng = sensor_data['engine']
                data_dict['engine_rpm'] = int(eng.get('rpm', 0))
                data_dict['engine_temp'] = int(eng.get('temperature', 0))
                data_dict['oil_pressure'] = int(eng.get('oil_pressure', 0) * 10)  # 0.1 bar 단위
                data_dict['engine_load'] = int(eng.get('load', 0))

            # Fuel 데이터
            if 'fuel' in sensor_data:
                fuel = sensor_data['fuel']
                data_dict['fuel_level'] = int(fuel.get('level', 0))
                data_dict['fuel_consumption'] = int(fuel.get('consumption_rate', 0) * 10)  # 0.1 L/h 단위
                data_dict['fuel_temp'] = int(fuel.get('temperature', 0))

            # Cooling 데이터
            if 'cooling' in sensor_data:
                cool = sensor_data['cooling']
                data_dict['coolant_temp'] = int(cool.get('temperature', 0))
                data_dict['coolant_pressure'] = int(cool.get('pressure', 0) * 10)  # 0.1 bar 단위

            # Electrical 데이터
            if 'electrical' in sensor_data:
                elec = sensor_data['electrical']
                data_dict['battery_voltage'] = int(elec.get('battery_voltage', 0) * 10)  # 0.1V 단위

            # Navigation 데이터
            if 'navigation' in sensor_data:
                nav = sensor_data['navigation']
                # 키 각도는 -35~+35 범위이므로 +50 offset을 줘서 양수로 만듦
                data_dict['rudder_angle'] = int(nav.get('rudder_angle', 0) + 50)
                data_dict['water_depth'] = int(nav.get('water_depth', 0))

            return data_dict

        except json.JSONDecodeError as e:
            log.error(f"[Sensor→PLC] JSON parse error: {e}")
            return None
        except Exception as e:
            log.error(f"[Sensor→PLC] Parse error: {e}")
            return None

    def write_to_plc(self, data):
        """센서 데이터를 PLC 레지스터에 쓰기"""
        try:
            written_count = 0

            for key, value in data.items():
                if key in self.register_map:
                    register_addr = self.register_map[key]
                    result = self.plc_client.write_register(register_addr, int(value))

                    if not result.isError():
                        written_count += 1
                    else:
                        log.error(f"[Sensor→PLC] Failed to write {key} to register {register_addr}")

            self.stats['written'] += written_count

            # 로그 출력 (주요 값만)
            log.info(
                f"[Sensor→PLC] Engine: RPM={data.get('engine_rpm', 'N/A')}, "
                f"Temp={data.get('engine_temp', 'N/A')}°C, "
                f"Oil={data.get('oil_pressure', 'N/A')/10:.1f}bar"
            )
            log.info(
                f"[Sensor→PLC] Fuel: Level={data.get('fuel_level', 'N/A')}%, "
                f"Flow={data.get('fuel_consumption', 'N/A')/10:.1f}L/h"
            )

            return True

        except Exception as e:
            log.error(f"[Sensor→PLC] Write error: {e}")
            self.stats['errors'] += 1
            return False

    def run(self):
        """메인 루프"""
        if not self.connect_plc():
            log.error("[Sensor→PLC] Cannot start without PLC connection")
            return

        log.info(f"[Sensor→PLC] Listening on UDP port {self.sensor_port}")
        log.info(f"[Sensor→PLC] Register mapping:")
        for name, addr in sorted(self.register_map.items(), key=lambda x: x[1]):
            log.info(f"  [{addr:3d}] {name}")

        try:
            while True:
                # 센서 데이터 수신
                data, addr = self.sock.recvfrom(4096)
                message = data.decode('utf-8', errors='ignore').strip()

                self.stats['received'] += 1

                # JSON 파싱
                parsed_data = self.parse_sensor_json(message)

                if parsed_data:
                    self.stats['parsed'] += 1

                    # PLC에 쓰기
                    self.write_to_plc(parsed_data)
                else:
                    log.warning(f"[Sensor→PLC] Failed to parse JSON message")

                # 30초마다 통계 출력
                if self.stats['received'] % 15 == 0:
                    log.info(f"\n[Sensor→PLC] === Statistics ===")
                    log.info(f"  Received: {self.stats['received']}")
                    log.info(f"  Parsed:   {self.stats['parsed']}")
                    log.info(f"  Written:  {self.stats['written']}")
                    log.info(f"  Errors:   {self.stats['errors']}")
                    log.info(f"================================\n")

        except KeyboardInterrupt:
            log.info("\n[Sensor→PLC] Shutting down...")
        finally:
            if self.plc_client:
                self.plc_client.close()
            self.sock.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Sensor to PLC Connector')
    parser.add_argument('--sensor-port', type=int, default=10112, help='Sensor data UDP port')
    parser.add_argument('--plc-host', default='localhost', help='PLC server host')
    parser.add_argument('--plc-port', type=int, default=502, help='PLC server port')

    args = parser.parse_args()

    connector = SensorToPLC(
        sensor_port=args.sensor_port,
        plc_host=args.plc_host,
        plc_port=args.plc_port
    )

    connector.run()
