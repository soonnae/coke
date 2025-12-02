"""
PLC Exporter (Prometheus Exporter)
PLC 데이터를 Prometheus 형식으로 내보내기
"""

from pymodbus.client import ModbusTcpClient
from prometheus_client import start_http_server, Gauge
import time
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class PLCExporter:
    def __init__(self, plc_host='localhost', plc_port=502, exporter_port=9100):
        self.plc_host = plc_host
        self.plc_port = plc_port
        self.exporter_port = exporter_port
        self.client = None
        
        # Prometheus Gauge 메트릭 정의
        self.metrics = {
            'engine_rpm': Gauge('ship_engine_rpm', 'Engine RPM'),
            'engine_target_rpm': Gauge('ship_engine_target_rpm', 'Engine Target RPM'),
            'engine_temp': Gauge('ship_engine_temperature_celsius', 'Engine Temperature'),
            'oil_pressure': Gauge('ship_oil_pressure_bar', 'Engine Oil Pressure'),
            'fuel_level': Gauge('ship_fuel_level_percent', 'Fuel Level'),
            'fuel_consumption': Gauge('ship_fuel_consumption_lph', 'Fuel Consumption Rate'),
            'rudder_angle': Gauge('ship_rudder_angle_degrees', 'Rudder Angle'),
            'engine_load': Gauge('ship_engine_load_percent', 'Engine Load'),
            'battery_voltage': Gauge('ship_battery_voltage_volts', 'Battery Voltage'),
            'water_depth': Gauge('ship_water_depth_meters', 'Water Depth'),
            'engine_running': Gauge('ship_engine_running', 'Engine Running Status (1=running, 0=stopped)'),
            'emergency_stop': Gauge('ship_emergency_stop', 'Emergency Stop Status (1=active, 0=inactive)'),
            'plc_connection': Gauge('ship_plc_connection_status', 'PLC Connection Status (1=connected, 0=disconnected)')
        }
        
    def connect(self):
        """PLC 서버에 연결"""
        try:
            self.client = ModbusTcpClient(self.plc_host, port=self.plc_port)
            if self.client.connect():
                log.info(f"[PLC Exporter] Connected to PLC at {self.plc_host}:{self.plc_port}")
                self.metrics['plc_connection'].set(1)
                return True
            else:
                log.error("[PLC Exporter] Failed to connect to PLC")
                self.metrics['plc_connection'].set(0)
                return False
        except Exception as e:
            log.error(f"[PLC Exporter] Connection error: {e}")
            self.metrics['plc_connection'].set(0)
            return False
    
    def disconnect(self):
        """PLC 연결 해제"""
        if self.client:
            self.client.close()
            log.info("[PLC Exporter] Disconnected from PLC")
            self.metrics['plc_connection'].set(0)
    
    def collect_metrics(self):
        """PLC에서 메트릭 수집"""
        try:
            # Holding Registers 읽기
            result = self.client.read_holding_registers(0, 10)
            
            if result.isError():
                log.error("[PLC Exporter] Error reading holding registers")
                self.metrics['plc_connection'].set(0)
                return False
            
            # 레지스터 값을 메트릭으로 변환
            self.metrics['engine_rpm'].set(result.registers[0])
            self.metrics['engine_target_rpm'].set(result.registers[1])
            self.metrics['engine_temp'].set(result.registers[2] / 10.0)
            self.metrics['oil_pressure'].set(result.registers[3] / 100.0)
            self.metrics['fuel_level'].set(result.registers[4] / 10.0)
            self.metrics['fuel_consumption'].set(result.registers[5] / 10.0)
            self.metrics['rudder_angle'].set(result.registers[6] / 10.0)
            self.metrics['engine_load'].set(result.registers[7])
            self.metrics['battery_voltage'].set(result.registers[8] / 10.0)
            self.metrics['water_depth'].set(result.registers[9] / 10.0)
            
            # Coils 읽기 (엔진 상태)
            coil_result = self.client.read_coils(0, 2)
            
            if not coil_result.isError():
                self.metrics['engine_running'].set(1 if coil_result.bits[0] else 0)
                self.metrics['emergency_stop'].set(1 if coil_result.bits[1] else 0)
            
            self.metrics['plc_connection'].set(1)
            return True
            
        except Exception as e:
            log.error(f"[PLC Exporter] Error collecting metrics: {e}")
            self.metrics['plc_connection'].set(0)
            return False
    
    def run(self):
        """Exporter 메인 루프"""
        # Prometheus HTTP 서버 시작
        start_http_server(self.exporter_port)
        log.info(f"[PLC Exporter] Prometheus exporter started on port {self.exporter_port}")
        log.info(f"[PLC Exporter] Metrics available at http://localhost:{self.exporter_port}/metrics")
        
        # PLC 연결 재시도 설정
        retry_delay = 5
        connected = False
        
        try:
            while True:
                # PLC에 연결되지 않은 경우 재연결 시도
                if not connected:
                    connected = self.connect()
                    if not connected:
                        log.warning(f"[PLC Exporter] Retrying connection in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                
                # 메트릭 수집
                success = self.collect_metrics()
                
                if not success:
                    log.warning("[PLC Exporter] Failed to collect metrics, reconnecting...")
                    self.disconnect()
                    connected = False
                    time.sleep(retry_delay)
                    continue
                
                # 주기적으로 상태 출력 (30초마다)
                if int(time.time()) % 30 == 0:
                    self.print_metrics()
                
                time.sleep(5)  # 5초마다 메트릭 수집
                
        except KeyboardInterrupt:
            log.info("\n[PLC Exporter] Shutting down...")
        finally:
            self.disconnect()
    
    def print_metrics(self):
        """현재 메트릭 출력"""
        log.info("\n" + "="*60)
        log.info("[PLC Exporter] Current Metrics")
        log.info("="*60)
        log.info(f"PLC Connection:      {self.metrics['plc_connection']._value.get()}")
        log.info(f"Engine Running:      {self.metrics['engine_running']._value.get()}")
        log.info(f"Emergency Stop:      {self.metrics['emergency_stop']._value.get()}")
        log.info(f"Engine RPM:          {self.metrics['engine_rpm']._value.get()}")
        log.info(f"Target RPM:          {self.metrics['engine_target_rpm']._value.get()}")
        log.info(f"Temperature:         {self.metrics['engine_temp']._value.get():.1f} °C")
        log.info(f"Oil Pressure:        {self.metrics['oil_pressure']._value.get():.2f} bar")
        log.info(f"Fuel Level:          {self.metrics['fuel_level']._value.get():.1f} %")
        log.info(f"Fuel Consumption:    {self.metrics['fuel_consumption']._value.get():.1f} L/h")
        log.info(f"Engine Load:         {self.metrics['engine_load']._value.get()} %")
        log.info(f"Battery Voltage:     {self.metrics['battery_voltage']._value.get():.1f} V")
        log.info(f"Rudder Angle:        {self.metrics['rudder_angle']._value.get():.1f} °")
        log.info(f"Water Depth:         {self.metrics['water_depth']._value.get():.1f} m")
        log.info("="*60 + "\n")

if __name__ == "__main__":
    exporter = PLCExporter(
        plc_host='localhost',
        plc_port=502,
        exporter_port=9100
    )
    exporter.run()
