"""
PLC Server (Modbus TCP Server)
Control Zone - Software PLC
레지스터 4개 + Coil 1개만 유지
"""

from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class PLCServer:
    def __init__(self, host='0.0.0.0', port=502):
        self.host = host
        self.port = port
        
        initial_registers = [800, 50, 1, 0]
        initial_coils = [True]
        
        self.store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0]*10),
            co=ModbusSequentialDataBlock(0, initial_coils + [False]*9),
            hr=ModbusSequentialDataBlock(0, initial_registers + [0]*96),
            ir=ModbusSequentialDataBlock(0, [0]*10)
        )
        
        self.context = ModbusServerContext(slaves=self.store, single=True)
        
    def start(self):
        log.info(f"[PLC Server] Starting on {self.host}:{self.port}")
        log.info("[PLC Server] Registers:")
        log.info("  0: RPM (800)")
        log.info("  1: Ballast Level (50)")
        log.info("  2: Pump Status (1)")
        log.info("  3: Rudder Angle (0)")
        log.info("[PLC Server] Coils:")
        log.info("  0: Pump ON/OFF (True)")
        
        try:
            StartTcpServer(
                context=self.context,
                address=(self.host, self.port),
                allow_reuse_address=True
            )
        except Exception as e:
            log.error(f"[PLC Server] Error: {e}")

if __name__ == "__main__":
    server = PLCServer(host='0.0.0.0', port=502)
    server.start()
