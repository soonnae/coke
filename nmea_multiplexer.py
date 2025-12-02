"""
NMEA Multiplexer
여러 소스의 NMEA 데이터를 수집하고 통합하여 재전송
"""

import socket
import threading
import time
import queue
from datetime import datetime

class NMEAMultiplexer:
    def __init__(self, output_host='0.0.0.0', output_port=10113):
        self.output_host = output_host
        self.output_port = output_port
        self.output_socket = None
        
        # 입력 소스 설정
        self.input_sources = [
            {'name': 'GPS', 'host': 'localhost', 'port': 10110},
            {'name': 'AIS', 'host': 'localhost', 'port': 10111},
            {'name': 'Sensor', 'host': 'localhost', 'port': 10112}
        ]
        
        # 데이터 큐
        self.data_queue = queue.Queue()
        
        # 클라이언트 목록
        self.clients = []
        self.clients_lock = threading.Lock()
        
        # 통계
        self.stats = {
            'messages_received': 0,
            'messages_sent': 0,
            'clients_connected': 0
        }
        
    def start(self):
        """멀티플렉서 시작"""
        print("[NMEA Multiplexer] Starting...")
        
        # 출력 서버 시작
        output_thread = threading.Thread(target=self.start_output_server, daemon=True)
        output_thread.start()
        
        # 입력 소스 연결
        for source in self.input_sources:
            thread = threading.Thread(
                target=self.connect_to_source,
                args=(source,),
                daemon=True
            )
            thread.start()
        
        # 데이터 배포 스레드
        distribute_thread = threading.Thread(target=self.distribute_data, daemon=True)
        distribute_thread.start()
        
        # 통계 출력 스레드
        stats_thread = threading.Thread(target=self.print_stats, daemon=True)
        stats_thread.start()
        
        # 메인 루프
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[NMEA Multiplexer] Shutting down...")
            self.shutdown()
    
    def start_output_server(self):
        """출력 서버 시작 (클라이언트가 연결)"""
        self.output_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.output_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.output_socket.bind((self.output_host, self.output_port))
        self.output_socket.listen(10)
        print(f"[NMEA Multiplexer] Output server started on {self.output_host}:{self.output_port}")
        
        while True:
            try:
                client_socket, addr = self.output_socket.accept()
                print(f"[NMEA Multiplexer] Client connected: {addr}")
                
                with self.clients_lock:
                    self.clients.append({
                        'socket': client_socket,
                        'address': addr,
                        'connected_at': datetime.now()
                    })
                    self.stats['clients_connected'] = len(self.clients)
                    
            except Exception as e:
                print(f"[NMEA Multiplexer] Error accepting client: {e}")
                break
    
    def connect_to_source(self, source):
        """입력 소스에 연결"""
        retry_delay = 5
        
        while True:
            try:
                print(f"[NMEA Multiplexer] Connecting to {source['name']} ({source['host']}:{source['port']})")
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((source['host'], source['port']))
                
                print(f"[NMEA Multiplexer] Connected to {source['name']}")
                
                # 데이터 수신
                buffer = ""
                while True:
                    data = sock.recv(4096).decode('utf-8')
                    if not data:
                        break
                    
                    buffer += data
                    
                    # 줄 단위로 처리
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line:
                            # 소스 정보와 함께 큐에 추가
                            self.data_queue.put({
                                'source': source['name'],
                                'data': line,
                                'timestamp': datetime.now()
                            })
                            self.stats['messages_received'] += 1
                
                print(f"[NMEA Multiplexer] Disconnected from {source['name']}")
                sock.close()
                
            except ConnectionRefusedError:
                print(f"[NMEA Multiplexer] Cannot connect to {source['name']}, retrying in {retry_delay}s...")
            except Exception as e:
                print(f"[NMEA Multiplexer] Error with {source['name']}: {e}")
            
            time.sleep(retry_delay)
    
    def distribute_data(self):
        """데이터를 연결된 클라이언트에 배포"""
        while True:
            try:
                # 큐에서 데이터 가져오기 (타임아웃 1초)
                item = self.data_queue.get(timeout=1)
                
                # 모든 클라이언트에 전송
                disconnected_clients = []
                
                with self.clients_lock:
                    for client in self.clients:
                        try:
                            # 소스 정보를 포함한 메시지 생성
                            message = f"[{item['source']}] {item['data']}\n"
                            client['socket'].send(message.encode('utf-8'))
                            self.stats['messages_sent'] += 1
                            
                        except Exception as e:
                            print(f"[NMEA Multiplexer] Error sending to {client['address']}: {e}")
                            disconnected_clients.append(client)
                    
                    # 끊어진 클라이언트 제거
                    for client in disconnected_clients:
                        print(f"[NMEA Multiplexer] Removing disconnected client: {client['address']}")
                        try:
                            client['socket'].close()
                        except:
                            pass
                        self.clients.remove(client)
                    
                    self.stats['clients_connected'] = len(self.clients)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[NMEA Multiplexer] Error distributing data: {e}")
    
    def print_stats(self):
        """주기적으로 통계 출력"""
        while True:
            time.sleep(30)  # 30초마다
            print(f"\n[NMEA Multiplexer] Statistics:")
            print(f"  Messages Received: {self.stats['messages_received']}")
            print(f"  Messages Sent: {self.stats['messages_sent']}")
            print(f"  Connected Clients: {self.stats['clients_connected']}\n")
    
    def shutdown(self):
        """멀티플렉서 종료"""
        with self.clients_lock:
            for client in self.clients:
                try:
                    client['socket'].close()
                except:
                    pass
        
        if self.output_socket:
            self.output_socket.close()

if __name__ == "__main__":
    multiplexer = NMEAMultiplexer(output_host='0.0.0.0', output_port=10113)
    multiplexer.start()
