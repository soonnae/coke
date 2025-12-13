"""
Engine Logic Controller
Control Zone - Engine Telemetry Module
RPM, Ballast, Pump만 간단히 변화
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
        
        # 초기값
        self.rpm = 800
        self.ballast = 50
        self.pump_status = 1
        
        # 순환 패턴
        self.rpm_target = [800, 1000, 1200, 900]
        self.ballast_target = [40, 45, 50, 45]

        self.rpm_index = 0
        self.ballast_index = 0
        
    def connect(self):
        """PLC 서버 연결"""
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
                self.update_values(iteration)
                self.write_to_plc()
                iteration += 1
                time.sleep(2)
                
        except KeyboardInterrupt:
            log.info("\n[Engine Logic] Shutting down...")
        finally:
            self.disconnect()
    
    def update_values(self, iteration):
        """값 업데이트"""
        if iteration % 5 == 0:
            self.rpm = self.rpm_target[self.rpm_index]
            self.rpm_index = (self.rpm_index + 1) % len(self.rpm_target)
            
            self.ballast = self.ballast_target[self.ballast_index]
            self.ballast_index = (self.ballast_index + 1) % len(self.ballast_target)
            
            self.pump_status = 1 - self.pump_status  # ON/OFF toggle
    
    def write_to_plc(self):
        """PLC에 값 쓰기 (안정 버전)"""
        try:
            # Holding Registers 개별 쓰기
            self.client.write_register(0, int(self.rpm))
            self.client.write_register(1, int(self.ballast))
            self.client.write_register(2, int(self.pump_status))

            # Coil 쓰기
            self.client.write_coil(0, bool(self.pump_status))

            log.info(
                f"[Engine Logic] RPM={self.rpm}, "
                f"Ballast={self.ballast}, "
                f"Pump={'ON' if self.pump_status else 'OFF'}"
            )

        except Exception as e:
            log.error(f"[Engine Logic] Write error: {e}")
            # 연결 끊김 감지 시 재연결 시도
            log.warning("[Engine Logic] Attempting to reconnect...")
            self.disconnect()
            time.sleep(2)
            if not self.connect():
                log.error("[Engine Logic] Reconnection failed")

if __name__ == "__main__":
    engine = EngineLogic(plc_host='localhost', plc_port=502)
    engine.run()
