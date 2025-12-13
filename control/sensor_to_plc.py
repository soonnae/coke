"""
Sensor to PLC Connector
Field Zone Sensor Simulator 데이터를 Control Zone PLC로 연결
UDP로 센서 데이터를 수신하여 Modbus 레지스터에 매핑
"""

from pymodbus.client import ModbusTcpClient
import socket
import json
import logging
import time
import re

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
        # 기존: 0=RPM, 1=Ballast, 2=Pump
        # 추가: 10~20번 레지스터에 센서 데이터 매핑
        self.register_map = {
            'engine_rpm': 10,           # 엔진 RPM (센서 데이터)
            'engine_temp': 11,          # 엔진 온도
            'oil_pressure': 12,         # 오일 압력
            'fuel_level': 13,           # 연료 레벨
            'fuel_flow': 14,            # 연료 흐름
            'coolant_temp': 15,         # 냉각수 온도
            'coolant_pressure': 16,     # 냉각수 압력
            'battery_voltage': 17,      # 배터리 전압 (x10)
            'battery_current': 18,      # 배터리 전류
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

    def parse_sensor_message(self, message):
        """
        센서 메시지 파싱
        형식: "ENGINE: RPM=850, Temp=75°C, Oil=4.2bar | FUEL: Level=80%, Flow=12L/h | ..."
        """
        data = {}

        try:
            # ENGINE 섹션
            engine_match = re.search(r'ENGINE:\s*RPM=(\d+),\s*Temp=(\d+)', message)
            if engine_match:
                data['engine_rpm'] = int(engine_match.group(1))
                data['engine_temp'] = int(engine_match.group(2))

            # Oil Pressure
            oil_match = re.search(r'Oil=([\d.]+)bar', message)
            if oil_match:
                data['oil_pressure'] = int(float(oil_match.group(1)) * 10)  # 0.1bar 단위

            # FUEL 섹션
            fuel_level_match = re.search(r'FUEL:\s*Level=(\d+)%', message)
            if fuel_level_match:
                data['fuel_level'] = int(fuel_level_match.group(1))

            fuel_flow_match = re.search(r'Flow=(\d+)L/h', message)
            if fuel_flow_match:
                data['fuel_flow'] = int(fuel_flow_match.group(1))

            # COOLING 섹션
            coolant_temp_match = re.search(r'COOLING:\s*Temp=(\d+)', message)
            if coolant_temp_match:
                data['coolant_temp'] = int(coolant_temp_match.group(1))

            coolant_pressure_match = re.search(r'COOLING:.*Pressure=([\d.]+)bar', message)
            if coolant_pressure_match:
                data['coolant_pressure'] = int(float(coolant_pressure_match.group(1)) * 10)

            # ELECTRICAL 섹션
            voltage_match = re.search(r'ELECTRICAL:\s*Voltage=([\d.]+)V', message)
            if voltage_match:
                data['battery_voltage'] = int(float(voltage_match.group(1)) * 10)  # 0.1V 단위

            current_match = re.search(r'Current=([\d.]+)A', message)
            if current_match:
                data['battery_current'] = int(float(current_match.group(1)) * 10)  # 0.1A 단위

            return data

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
            log.info(f"[Sensor→PLC] Written {written_count} values to PLC")

            # 로그 출력 (주요 값만)
            if 'engine_rpm' in data:
                log.info(f"  Engine: RPM={data.get('engine_rpm', 'N/A')}, Temp={data.get('engine_temp', 'N/A')}°C")
            if 'fuel_level' in data:
                log.info(f"  Fuel: Level={data.get('fuel_level', 'N/A')}%, Flow={data.get('fuel_flow', 'N/A')}L/h")

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

                # 메시지 파싱
                parsed_data = self.parse_sensor_message(message)

                if parsed_data:
                    self.stats['parsed'] += 1

                    # PLC에 쓰기
                    self.write_to_plc(parsed_data)
                else:
                    log.warning(f"[Sensor→PLC] Failed to parse message")

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
