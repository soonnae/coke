"""
PLC Server (Modbus TCP)
STATE ONLY PLC

HR[0] RPM
HR[1] Ballast x10
HR[2] Pump Mode (uint16)

Sensor Data Registers (10-21):
HR[10] Engine RPM
HR[11] Engine Temperature
HR[12] Oil Pressure (x10)
HR[13] Engine Load (%)
HR[14] Fuel Level (%)
HR[15] Fuel Consumption (x10)
HR[16] Fuel Temperature
HR[17] Coolant Temperature
HR[18] Coolant Pressure (x10)
HR[19] Battery Voltage (x10)
HR[20] Rudder Angle (+50 offset)
HR[21] Water Depth
"""

from pymodbus.server.sync import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class PLCServer:
    def __init__(self, host="0.0.0.0", port=502):
        # Initialize holding registers (0-29, total 30 registers)
        # Registers 0-2: Engine control (used by engine_logic.py)
        # Registers 10-21: Sensor data (used by sensor_to_plc.py)
        initial_hr = [0] * 30
        initial_hr[0] = 800   # RPM
        initial_hr[1] = 450   # Ballast = 45.0
        initial_hr[2] = 0     # Pump = HOLD

        store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0]*10),
            co=ModbusSequentialDataBlock(0, [False]*10),
            hr=ModbusSequentialDataBlock(0, initial_hr),
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
