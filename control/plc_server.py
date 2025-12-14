"""
PLC Server (Modbus TCP Server)
Control Zone - Minimal Software PLC
Registers: RPM, Ballast, Pump
Coils: Pump ON/OFF
Compatible with pymodbus 2.5.3
"""

from pymodbus.server.sync import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class PLCServer:
    def __init__(self, host='0.0.0.0', port=502):
        self.host = host
        self.port = port

        # Minimal registers
        initial_registers = [
            800,   # 0: RPM
            50,    # 1: Ballast Level
            1      # 2: Pump Status (1=ON)
        ]

        # Coil for Pump ON/OFF
        initial_coils = [True]

        # Create Modbus datastore (pymodbus 2.x)
        store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0]*100),                     # Discrete Inputs
            co=ModbusSequentialDataBlock(0, initial_coils + [False]*99),  # Coils
            hr=ModbusSequentialDataBlock(0, initial_registers + [0]*97),  # Holding Registers
            ir=ModbusSequentialDataBlock(0, [0]*100)                      # Input Registers
        )

        self.context = ModbusServerContext(slaves=store, single=True)

    def start(self):
        log.info(f"[PLC Server] Starting on {self.host}:{self.port}")
        log.info("[PLC Server] Holding Registers:")
        log.info("  0: RPM (800)")
        log.info("  1: Ballast Level (50)")
        log.info("  2: Pump Status (1)")
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
