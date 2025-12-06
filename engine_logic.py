"""
Engine Logic Controller
Control Zone - Engine Telemetry Module
RPM, Ballast, Pump, Rudder만 간단히 변화
"""

from pymodbus.client import ModbusTcpClient
import time
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class EngineLogic:
    def __init__(self, plc_host='localhost', plc_port=502):
        self.plc_host = plc_host
        self.plc_port = plc_port
        self.client = None
        
        # 간단한 변수 4개
        self.rpm = 800
        self.ballast = 50
        self.pump_status = 1
        self.rudder = 0
        
        # 변화 패턴
        self.rpm_target = [800, 1000, 1200, 900]
        self.rpm_index = 0
        
        self.ballast_target = [40, 45, 50, 45]
        self.ballast_index = 0
        
        self.rudder_target = [-5, 0, 5, 0]
        self.rudder_index = 0
        
        self.pump_toggle_count = 0
        
    def connect(self):
        """PLC 연결"""
        try:
            self.client = ModbusTcpClient(self.plc_host, port=self.plc_port)
            if self.client.connect():
                log.info(f"[Engine Logic] Connected to PLC at {self.plc_host}:{self.plc_port}")
                return True
            else:
                log.error("[Engine Logic] Failed to connect to PLC")
                return False
        except Exception as e:
            log.error(f"[Engine Logic] Connection error: {e}")
            return False
    
    def disconnect(self):
        """PLC 연결 해제"""
        if self.client:
            self.client.close()
    
    def run(self):
        """메인 루프"""
        if not self.connect():
            return
        
        log.info("[Engine Logic] Starting simple control loop")
        
        try:
            iteration = 0
            while True:
                # 값 업데이트
                self.update_values(iteration)
                
                # PLC에 쓰기
                self.write_to_plc()
                
                iteration += 1
                time.sleep(2)  # 2초마다
                
        except KeyboardInterrupt:
            log.info("\n[Engine Logic] Shutting down...")
        finally:
            self.disconnect()
    
    def update_values(self, iteration):
        """간단한 값 변화"""
        # RPM: 10초마다 다음 목표로
        if iteration % 5 == 0:
            self.rpm = self.rpm_target[self.rpm_index]
            self.rpm_index = (self.rpm_index + 1) % len(self.rpm_target)
        
        # Ballast: 10초마다 변화
        if iteration % 5 == 0:
            self.ballast = self.ballast_target[self.ballast_index]
            self.ballast_index = (self.ballast_index + 1) % len(self.ballast_target)
        
        # Pump: 10초마다 ON/OFF 토글
        if iteration % 5 == 0:
            self.pump_status = 1 - self.pump_status
            self.pump_toggle_count += 1
        
        # Rudder: 10초마다 변화
        if iteration % 5 == 0:
            self.rudder = self.rudder_target[self.rudder_index]
            self.rudder_index = (self.rudder_index + 1) % len(self.rudder_target)
    
    def write_to_plc(self):
        """PLC에 레지스터 쓰기"""
        try:
            # Holding Registers 0-3
            values = [
                int(self.rpm),
                int(self.ballast),
                int(self.pump_status),
                int(self.rudder)
            ]
            self.client.write_registers(0, values)
            
            # Coil 0 (Pump ON/OFF)
            self.client.write_coil(0, bool(self.pump_status))
            
            log.info(f"[Engine Logic] RPM={self.rpm}, Ballast={self.ballast}, Pump={'ON' if self.pump_status else 'OFF'}, Rudder={self.rudder}")
            
        except Exception as e:
            log.error(f"[Engine Logic] Write error: {e}")

if __name__ == "__main__":
    engine = EngineLogic(plc_host='localhost', plc_port=502)
    engine.run()
