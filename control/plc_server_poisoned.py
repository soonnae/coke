#!/usr/bin/env python3
"""
PLC Server (Poisoned Initialization Version)
시나리오: Initialization Poisoning Attack

⚠️ 이 버전은 초기 PLC 레지스터 값이 의도적으로 오염된 상태로 시작합니다.
   정상 버전과 비교 시연용으로만 사용하세요.

차이점:
- 정상: RPM=800, Ballast=50, Pump=1
- 오염: RPM=750, Ballast=45, Pump=1

효과:
- 시작 시점부터 엔진 기준값이 틀림
- Engine Logic이 이 값을 기준으로 동작
- 모든 제어 로직이 잘못된 baseline 기반으로 실행
- HMI/Dashboard가 틀린 값을 "정상"으로 표시
"""

from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# 초기화 오염 상수
RPM_OFFSET = -50      # RPM 50 낮게 시작 (800 -> 750)
BALLAST_OFFSET = -5   # Ballast 5 낮게 시작 (50 -> 45)

class PLCServerPoisoned:
    def __init__(self, host='0.0.0.0', port=502):
        self.host = host
        self.port = port

        # ⚠️ 오염된 초기 레지스터 값
        # 정상: [800, 50, 1]
        # 오염: offset 추가
        initial_registers = [
            800 + RPM_OFFSET,        # 0: RPM (750 instead of 800)
            50 + BALLAST_OFFSET,     # 1: Ballast Level (45 instead of 50)
            1                        # 2: Pump Status (1=ON, 정상 유지)
        ]

        # Coil for Pump ON/OFF (정상 유지)
        initial_coils = [True]

        # Create Modbus datastore
        self.store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0]*10),                     # Discrete Inputs
            co=ModbusSequentialDataBlock(0, initial_coils + [False]*9),  # Coils
            hr=ModbusSequentialDataBlock(0, initial_registers + [0]*97), # Holding Registers
            ir=ModbusSequentialDataBlock(0, [0]*10)                      # Input Registers
        )

        self.context = ModbusServerContext(slaves=self.store, single=True)

        # 오염 정보 저장
        self.normal_registers = [800, 50, 1]
        self.poisoned_registers = initial_registers

    def start(self):
        log.info("="*60)
        log.info("⚠️  PLC Server - POISONED INITIALIZATION")
        log.info("="*60)
        log.info(f"[PLC Server] Starting on {self.host}:{self.port}")
        log.info("")
        log.info("[WARNING] Initial registers are INTENTIONALLY INCORRECT:")
        log.info("")
        log.info("  Register 0 (RPM):")
        log.info(f"    Normal:   {self.normal_registers[0]}")
        log.info(f"    Poisoned: {self.poisoned_registers[0]} (offset: {RPM_OFFSET})")
        log.info("")
        log.info("  Register 1 (Ballast Level):")
        log.info(f"    Normal:   {self.normal_registers[1]}")
        log.info(f"    Poisoned: {self.poisoned_registers[1]} (offset: {BALLAST_OFFSET})")
        log.info("")
        log.info("  Register 2 (Pump Status):")
        log.info(f"    Normal:   {self.normal_registers[2]}")
        log.info(f"    Poisoned: {self.poisoned_registers[2]} (unchanged)")
        log.info("")
        log.info("[PLC Server] Coils:")
        log.info("  0: Pump ON/OFF (True)")
        log.info("="*60)

        try:
            StartTcpServer(
                context=self.context,
                address=(self.host, self.port),
                allow_reuse_address=True
            )
        except Exception as e:
            log.error(f"[PLC Server] Error: {e}")

if __name__ == "__main__":
    print()
    print("="*60)
    print("Initialization Poisoning Attack - PLC Server")
    print("Educational Demonstration - Incorrect Startup Configuration")
    print("="*60)
    print()

    server = PLCServerPoisoned(host='0.0.0.0', port=502)
    server.start()
