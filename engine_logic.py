"""
Engine Logic Controller
엔진 로직 제어 (PLC 서버와 연동하여 엔진 상태 관리)
"""

from pymodbus.client import ModbusTcpClient
import time
import random
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class EngineLogic:
    def __init__(self, plc_host='localhost', plc_port=502):
        self.plc_host = plc_host
        self.plc_port = plc_port
        self.client = None
        
        # 엔진 파라미터
        self.current_rpm = 850
        self.target_rpm = 850
        self.engine_temp = 60.0
        self.oil_pressure = 4.5
        self.fuel_level = 75.0
        self.fuel_consumption = 12.5
        self.rudder_angle = 0.0
        self.engine_load = 60
        self.battery_voltage = 24.5
        self.water_depth = 50.0
        
        # 엔진 상태
        self.engine_running = True
        self.emergency_stop = False
        
        # 안전 임계값
        self.MAX_TEMP = 105.0
        self.MIN_OIL_PRESSURE = 3.0
        self.MIN_FUEL_LEVEL = 10.0
        self.MAX_RPM = 1200
        self.MIN_RPM = 600
        
    def connect(self):
        """PLC 서버에 연결"""
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
            log.info("[Engine Logic] Disconnected from PLC")
    
    def run(self):
        """엔진 로직 메인 루프"""
        if not self.connect():
            log.error("[Engine Logic] Cannot start without PLC connection")
            return
        
        log.info("[Engine Logic] Starting engine control loop")
        
        try:
            iteration = 0
            while True:
                # PLC에서 현재 상태 읽기
                self.read_from_plc()
                
                # 엔진 로직 실행
                self.update_engine_state()
                
                # 안전 체크
                self.safety_check()
                
                # PLC에 업데이트된 값 쓰기
                self.write_to_plc()
                
                # 주기적으로 상태 출력 (10초마다)
                if iteration % 5 == 0:
                    self.print_status()
                
                iteration += 1
                time.sleep(2)  # 2초마다 업데이트
                
        except KeyboardInterrupt:
            log.info("\n[Engine Logic] Shutting down...")
        finally:
            self.disconnect()
    
    def read_from_plc(self):
        """PLC에서 레지스터 값 읽기"""
        try:
            # Holding Registers 읽기 (주소 0-9)
            result = self.client.read_holding_registers(0, 10)
            
            if not result.isError():
                self.current_rpm = result.registers[0]
                self.target_rpm = result.registers[1]
                self.engine_temp = result.registers[2] / 10.0
                self.oil_pressure = result.registers[3] / 100.0
                self.fuel_level = result.registers[4] / 10.0
                self.fuel_consumption = result.registers[5] / 10.0
                self.rudder_angle = result.registers[6] / 10.0
                self.engine_load = result.registers[7]
                self.battery_voltage = result.registers[8] / 10.0
                self.water_depth = result.registers[9] / 10.0
            
            # Coils 읽기 (엔진 상태)
            coil_result = self.client.read_coils(0, 2)
            if not coil_result.isError():
                self.engine_running = coil_result.bits[0]
                self.emergency_stop = coil_result.bits[1]
                
        except Exception as e:
            log.error(f"[Engine Logic] Error reading from PLC: {e}")
    
    def write_to_plc(self):
        """PLC에 레지스터 값 쓰기"""
        try:
            # Holding Registers 쓰기
            values = [
                int(self.current_rpm),
                int(self.target_rpm),
                int(self.engine_temp * 10),
                int(self.oil_pressure * 100),
                int(self.fuel_level * 10),
                int(self.fuel_consumption * 10),
                int(self.rudder_angle * 10),
                int(self.engine_load),
                int(self.battery_voltage * 10),
                int(self.water_depth * 10)
            ]
            
            self.client.write_registers(0, values)
            
            # Coils 쓰기
            self.client.write_coil(0, self.engine_running)
            self.client.write_coil(1, self.emergency_stop)
            
        except Exception as e:
            log.error(f"[Engine Logic] Error writing to PLC: {e}")
    
    def update_engine_state(self):
        """엔진 상태 업데이트"""
        if self.emergency_stop or not self.engine_running:
            # 비상 정지 또는 엔진 꺼짐
            self.current_rpm = max(0, self.current_rpm - 100)
            self.engine_temp = max(25, self.engine_temp - 2)
            return
        
        # RPM 조정 (목표 RPM으로 서서히 변화)
        rpm_diff = self.target_rpm - self.current_rpm
        if abs(rpm_diff) > 50:
            self.current_rpm += 50 if rpm_diff > 0 else -50
        else:
            self.current_rpm = self.target_rpm
        
        # 엔진 온도 (RPM과 부하에 따라 변화)
        target_temp = 60 + (self.current_rpm - 600) / 60 + self.engine_load / 10
        temp_diff = target_temp - self.engine_temp
        self.engine_temp += temp_diff * 0.1  # 서서히 변화
        
        # 랜덤 변동
        self.engine_temp += random.uniform(-1, 1)
        
        # 오일 압력 (RPM에 비례)
        base_pressure = 3.0 + (self.current_rpm - 600) / 300
        self.oil_pressure = base_pressure + random.uniform(-0.2, 0.2)
        
        # 연료 소비
        self.fuel_consumption = 8 + (self.current_rpm / 100) + (self.engine_load / 20)
        self.fuel_level -= self.fuel_consumption / 3600  # 시간당 소비량
        self.fuel_level = max(0, self.fuel_level)
        
        # 엔진 부하 (RPM에 따라 변화)
        self.engine_load = int(50 + (self.current_rpm - 600) / 10 + random.uniform(-5, 5))
        self.engine_load = max(30, min(100, self.engine_load))
        
        # 배터리 전압
        self.battery_voltage += random.uniform(-0.3, 0.3)
        self.battery_voltage = max(22.0, min(28.0, self.battery_voltage))
        
        # 키 각도
        self.rudder_angle += random.uniform(-5, 5)
        self.rudder_angle = max(-35, min(35, self.rudder_angle))
        
        # 수심
        self.water_depth += random.uniform(-3, 3)
        self.water_depth = max(10, min(200, self.water_depth))
    
    def safety_check(self):
        """안전 체크 및 비상 조치"""
        alarms = []
        
        # 온도 체크
        if self.engine_temp > self.MAX_TEMP:
            alarms.append(f"CRITICAL: Engine temperature too high ({self.engine_temp:.1f}°C)")
            self.target_rpm = max(self.MIN_RPM, self.target_rpm - 100)
        
        # 오일 압력 체크
        if self.oil_pressure < self.MIN_OIL_PRESSURE:
            alarms.append(f"CRITICAL: Oil pressure too low ({self.oil_pressure:.2f} bar)")
            self.emergency_stop = True
        
        # 연료 체크
        if self.fuel_level < self.MIN_FUEL_LEVEL:
            alarms.append(f"WARNING: Fuel level critical ({self.fuel_level:.1f}%)")
        
        # RPM 범위 체크
        if self.target_rpm > self.MAX_RPM:
            alarms.append(f"WARNING: Target RPM too high, limiting to {self.MAX_RPM}")
            self.target_rpm = self.MAX_RPM
        elif self.target_rpm < self.MIN_RPM and self.target_rpm > 0:
            alarms.append(f"WARNING: Target RPM too low, setting to {self.MIN_RPM}")
            self.target_rpm = self.MIN_RPM
        
        # 알람 출력
        if alarms:
            log.warning("\n" + "!"*50)
            for alarm in alarms:
                log.warning(f"[Engine Logic] {alarm}")
            log.warning("!"*50 + "\n")
    
    def print_status(self):
        """현재 상태 출력"""
        log.info("\n" + "="*60)
        log.info("[Engine Logic] Status Report")
        log.info("="*60)
        log.info(f"Engine Running:      {'YES' if self.engine_running else 'NO'}")
        log.info(f"Emergency Stop:      {'ACTIVE' if self.emergency_stop else 'NO'}")
        log.info(f"Current RPM:         {self.current_rpm} RPM")
        log.info(f"Target RPM:          {self.target_rpm} RPM")
        log.info(f"Engine Temperature:  {self.engine_temp:.1f} °C")
        log.info(f"Oil Pressure:        {self.oil_pressure:.2f} bar")
        log.info(f"Fuel Level:          {self.fuel_level:.1f} %")
        log.info(f"Fuel Consumption:    {self.fuel_consumption:.1f} L/h")
        log.info(f"Engine Load:         {self.engine_load} %")
        log.info(f"Battery Voltage:     {self.battery_voltage:.1f} V")
        log.info(f"Rudder Angle:        {self.rudder_angle:.1f} °")
        log.info(f"Water Depth:         {self.water_depth:.1f} m")
        log.info("="*60 + "\n")

if __name__ == "__main__":
    engine = EngineLogic(plc_host='localhost', plc_port=502)
    engine.run()
