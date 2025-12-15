"""
PLC Server (Modbus TCP)
STATE ONLY PLC

HR[0] RPM
HR[1] Ballast x10
HR[2] Pump Mode (uint16)
"""

from pymodbus.server.sync import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class PLCServer:
    def __init__(self, host="0.0.0.0", port=502):
        store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0]*10),
            co=ModbusSequentialDataBlock(0, [False]*10),
            hr=ModbusSequentialDataBlock(0, [
                800,   # RPM
                450,   # Ballast = 45.0
                0      # Pump = HOLD
            ] + [0]*7),
            ir=ModbusSequentialDataBlock(0, [0]*10)
        )
        self.context = ModbusServerContext(slaves=store, single=True)
        self.host = host
        self.port = port

    def start(self):
        log.info("[PLC] STATE-ONLY PLC started")
        StartTcpServer(self.context, address=(self.host, self.port), allow_reuse_address=True)

if __name__ == "__main__":
    PLCServer().start()
