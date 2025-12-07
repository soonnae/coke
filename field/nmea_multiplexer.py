"""
NMEA Multiplexer
여러 소스의 UDP 데이터를 수신하고 통합하여 RouterOS로 재전송
"""

import socket
import threading
import time
from datetime import datetime

TARGET_IP = "10.10.10.10"
TARGET_PORT = 10113

class NMEAMultiplexer:
    def __init__(self):
        # UDP 수신 소켓들 (각 센서로부터)
        self.gps_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ais_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sensor_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # UDP 송신 소켓 (RouterOS로)
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 각 센서 포트 바인딩
        self.gps_sock.bind(('0.0.0.0', 10110))
        self.ais_sock.bind(('0.0.0.0', 10111))
        self.sensor_sock.bind(('0.0.0.0', 10112))
        
        # 통계
        self.stats = {
            'gps_received': 0,
            'ais_received': 0,
            'sensor_received': 0,
            'messages_sent': 0
        }
        
        self.running = True
        
    def start(self):
        """멀티플렉서 시작"""
        print("[NMEA Multiplexer] Starting UDP listeners...")
        print(f"[NMEA Multiplexer] GPS: 0.0.0.0:10110")
        print(f"[NMEA Multiplexer] AIS: 0.0.0.0:10111")
        print(f"[NMEA Multiplexer] Sensor: 0.0.0.0:10112")
        print(f"[NMEA Multiplexer] Forwarding to: {TARGET_IP}:{TARGET_PORT}")
        
        # 각 센서 데이터 수신 스레드
        threading.Thread(target=self.receive_gps, daemon=True).start()
        threading.Thread(target=self.receive_ais, daemon=True).start()
        threading.Thread(target=self.receive_sensor, daemon=True).start()
        
        # 통계 출력 스레드
        threading.Thread(target=self.print_stats, daemon=True).start()
        
        # 메인 루프
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[NMEA Multiplexer] Shutting down...")
            self.running = False
    
    def receive_gps(self):
        """GPS 데이터 수신 및 포워딩"""
        print("[NMEA Multiplexer] GPS listener started")
        while self.running:
            try:
                data, addr = self.gps_sock.recvfrom(4096)
                message = data.decode('utf-8').strip()
                print(f"[RECEIVE] GPS: {message}")
                
                # RouterOS로 포워딩
                self.forward_message("GPS", message)
                self.stats['gps_received'] += 1
                
            except Exception as e:
                if self.running:
                    print(f"[NMEA Multiplexer] GPS error: {e}")
    
    def receive_ais(self):
        """AIS 데이터 수신 및 포워딩"""
        print("[NMEA Multiplexer] AIS listener started")
        while self.running:
            try:
                data, addr = self.ais_sock.recvfrom(4096)
                message = data.decode('utf-8').strip()
                print(f"[RECEIVE] AIS: {message}")
                
                # RouterOS로 포워딩
                self.forward_message("AIS", message)
                self.stats['ais_received'] += 1
                
            except Exception as e:
                if self.running:
                    print(f"[NMEA Multiplexer] AIS error: {e}")
    
    def receive_sensor(self):
        """센서 데이터 수신 및 포워딩"""
        print("[NMEA Multiplexer] Sensor listener started")
        while self.running:
            try:
                data, addr = self.sensor_sock.recvfrom(4096)
                message = data.decode('utf-8').strip()
                print(f"[RECEIVE] SENSOR: {message}")
                
                # RouterOS로 포워딩
                self.forward_message("SENSOR", message)
                self.stats['sensor_received'] += 1
                
            except Exception as e:
                if self.running:
                    print(f"[NMEA Multiplexer] Sensor error: {e}")
    
    def forward_message(self, source, message):
        """메시지를 RouterOS로 포워딩"""
        try:
            # 소스 정보를 포함한 메시지 생성
            tagged_message = f"[{source}] {message}"
            self.send_sock.sendto(tagged_message.encode('utf-8'), (TARGET_IP, TARGET_PORT))
            self.stats['messages_sent'] += 1
            print(f"[FORWARD] {tagged_message}")
            
        except Exception as e:
            print(f"[NMEA Multiplexer] Forward error: {e}")
    
    def print_stats(self):
        """주기적으로 통계 출력"""
        while self.running:
            time.sleep(30)  # 30초마다
            print(f"\n[NMEA Multiplexer] Statistics:")
            print(f"  GPS Received:    {self.stats['gps_received']}")
            print(f"  AIS Received:    {self.stats['ais_received']}")
            print(f"  Sensor Received: {self.stats['sensor_received']}")
            print(f"  Messages Sent:   {self.stats['messages_sent']}\n")

if __name__ == "__main__":
    NMEAMultiplexer().start()
