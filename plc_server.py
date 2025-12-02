"""
PLC Server (Modbus TCP Server)
선박 엔진 제어를 위한 Modbus TCP 서버
"""

from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
import threading
import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class PLCServer:
    def __init__(self, host='0.0.0.0', port=502):
        self.host = host
        self.port = port
        
        # Modbus 데이터 저장소 초기화
        # Coils (읽기/쓰기 가능한 디지털 출력)
        self.coils = ModbusSequentialDataBlock(0, [0]*100)
        
        # Discrete Inputs (읽기 전용 디지털 입력)
        self.discrete_inputs = ModbusSequentialDataBlock(0, [0]*100)
        
        # Holding Registers (읽기/쓰기 가능한 아날로그 출력)
        # 초기값 설정
        initial_registers = [
            850,    # 0: Engine RPM (850 RPM)
            850,    # 1: Engine Target RPM
            600,    # 2: Engine Temperature (60.0°C, scaled by 10)
            450,    # 3: Engine Oil Pressure (4.5 bar, scaled by 100)
            750,    # 4: Fuel Level (75.0%, scaled by 10)
            125,    # 5: Fuel Consumption (12.5 L/h, scaled by 10)
            0,      # 6: Rudder Angle (0°, scaled by 10)
            100,    # 7: Engine Load (100%, scaled by 1)
            245,    # 8: Battery Voltage (24.5V, scaled by 10)
            500,    # 9: Water Depth (50.0m, scaled by 10)
        ] + [0]*90  # 나머지는 0으로 초기화
        self.holding_registers = ModbusSequentialDataBlock(0, initial_registers)
        
        # Input Registers (읽기 전용 아날로그 입력)
        self.input_registers = ModbusSequentialDataBlock(0, [0]*100)
        
        # 데이터 저장소 컨텍스트 생성
        self.store = ModbusSlaveContext(
            di=self.discrete_inputs,
            co=self.coils,
            hr=self.holding_registers,
            ir=self.input_registers
        )
        self.context = ModbusServerContext(slaves=self.store, single=True)
        
        # 디바이스 식별 정보
        self.identity = ModbusDeviceIdentification()
        self.identity.VendorName = 'CokE'
        self.identity.ProductCode = 'SHIP-PLC'
        self.identity.VendorUrl = 'http://github.com/coke'
        self.identity.ProductName = 'Ship Engine Controller'
        self.identity.ModelName = 'PLC-ENGINE-V1'
        self.identity.MajorMinorRevision = '1.0.0'
        
        self.server_thread = None
        self.running = False
        
    def start(self):
        """PLC 서버 시작"""
        log.info(f"[PLC Server] Starting on {self.host}:{self.port}")
        
        self.running = True
        
        # 서버를 별도 스레드에서 실행
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True
        )
        self.server_thread.start()
        
        log.info("[PLC Server] Started successfully")
        
        # 모니터링 루프
        try:
            while self.running:
                self.print_status()
                time.sleep(10)  # 10초마다 상태 출력
        except KeyboardInterrupt:
            log.info("\n[PLC Server] Shutting down...")
            self.running = False
    
    def _run_server(self):
        """Modbus TCP 서버 실행"""
        try:
            StartTcpServer(
                context=self.context,
                identity=self.identity,
                address=(self.host, self.port),
                allow_reuse_address=True
            )
        except Exception as e:
            log.error(f"[PLC Server] Error: {e}")
            self.running = False
    
    def print_status(self):
        """현재 PLC 상태 출력"""
        try:
            # Holding Registers 읽기
            result = self.store.getValues(3, 0, 10)  # Function code 3, address 0, count 10
            
            log.info("\n" + "="*50)
            log.info("[PLC Server] Current Status")
            log.info("="*50)
            log.info(f"Engine RPM:          {result[0]} RPM")
            log.info(f"Engine Target RPM:   {result[1]} RPM")
            log.info(f"Engine Temperature:  {result[2]/10:.1f} °C")
            log.info(f"Oil Pressure:        {result[3]/100:.2f} bar")
            log.info(f"Fuel Level:          {result[4]/10:.1f} %")
            log.info(f"Fuel Consumption:    {result[5]/10:.1f} L/h")
            log.info(f"Rudder Angle:        {result[6]/10:.1f} °")
            log.info(f"Engine Load:         {result[7]} %")
            log.info(f"Battery Voltage:     {result[8]/10:.1f} V")
            log.info(f"Water Depth:         {result[9]/10:.1f} m")
            
            # Coils 상태 확인
            coil_result = self.store.getValues(1, 0, 10)  # Function code 1, address 0, count 10
            log.info(f"\nCoils Status (0-9):  {coil_result}")
            
            log.info("="*50 + "\n")
            
        except Exception as e:
            log.error(f"[PLC Server] Error reading status: {e}")
    
    def get_register_value(self, address):
        """특정 레지스터 값 읽기"""
        try:
            result = self.store.getValues(3, address, 1)
            return result[0] if result else None
        except:
            return None
    
    def set_register_value(self, address, value):
        """특정 레지스터 값 쓰기"""
        try:
            self.store.setValues(3, address, [value])
            return True
        except:
            return False

if __name__ == "__main__":
    server = PLCServer(host='0.0.0.0', port=502)
    server.start()
