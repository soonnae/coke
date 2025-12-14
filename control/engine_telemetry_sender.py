"""
Engine Telemetry Sender
Control Zone → Bridge Zone 데이터 전송
PLC Modbus 데이터를 읽어서 Bridge Zone으로 NMEA XDR 형식 또는 JSON으로 전송
"""

from pymodbus.client.sync import ModbusTcpClient
import socket
import time
import logging
import json

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class EngineTelemetrySender:
    def __init__(self, plc_host='localhost', plc_port=502,
                 bridge_ip='10.10.10.10', bridge_port=10113,
                 format='nmea'):
        """
        Args:
            plc_host: PLC 서버 주소
            plc_port: PLC 서버 포트
            bridge_ip: Bridge Zone IP
            bridge_port: Bridge Zone 수신 포트
            format: 'nmea' 또는 'json'
        """
        self.plc_host = plc_host
        self.plc_port = plc_port
        self.bridge_ip = bridge_ip
        self.bridge_port = bridge_port
        self.format = format

        self.client = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def connect_plc(self):
        """PLC에 연결"""
        try:
            self.client = ModbusTcpClient(self.plc_host, port=self.plc_port)
            if self.client.connect():
                log.info(f"[Telemetry Sender] Connected to PLC at {self.plc_host}:{self.plc_port}")
                return True
            else:
                log.error("[Telemetry Sender] Failed to connect to PLC")
                return False
        except Exception as e:
            log.error(f"[Telemetry Sender] Connection error: {e}")
            return False

    def read_plc_data(self):
        """PLC에서 데이터 읽기"""
        try:
            # Holding Registers 읽기 (0: RPM, 1: Ballast, 2: Pump Status)
            result = self.client.read_holding_registers(0, 3)

            if result.isError():
                log.error("[Telemetry Sender] Failed to read registers")
                return None

            data = {
                'rpm': result.registers[0],
                'ballast': result.registers[1],
                'pump_status': result.registers[2],
                'timestamp': time.time()
            }

            return data

        except Exception as e:
            log.error(f"[Telemetry Sender] Read error: {e}")
            return None

    def format_as_nmea(self, data):
        """
        NMEA XDR 형식으로 변환
        XDR - Transducer Measurement
        Format: $--XDR,a,x.x,a,c--c, ..... *hh<CR><LF>
        """
        sentences = []

        # RPM
        xdr_rpm = f"$ECXDR,T,{data['rpm']},R,RPM"
        xdr_rpm += f"*{self.calculate_checksum(xdr_rpm[1:])}"
        sentences.append(xdr_rpm)

        # Ballast Level
        xdr_ballast = f"$ECXDR,V,{data['ballast']},P,BALLAST"
        xdr_ballast += f"*{self.calculate_checksum(xdr_ballast[1:])}"
        sentences.append(xdr_ballast)

        # Pump Status
        pump_state = "ON" if data['pump_status'] == 1 else "OFF"
        xdr_pump = f"$ECXDR,G,{data['pump_status']},S,PUMP_{pump_state}"
        xdr_pump += f"*{self.calculate_checksum(xdr_pump[1:])}"
        sentences.append(xdr_pump)

        return sentences

    def calculate_checksum(self, sentence):
        """NMEA 체크섬 계산"""
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)
        return f"{checksum:02X}"

    def format_as_json(self, data):
        """JSON 형식으로 변환"""
        return json.dumps(data)

    def send_to_bridge(self, data):
        """Bridge Zone으로 데이터 전송"""
        try:
            if self.format == 'nmea':
                sentences = self.format_as_nmea(data)
                for sentence in sentences:
                    message = sentence + "\r\n"
                    self.sock.sendto(message.encode('ascii'), (self.bridge_ip, self.bridge_port))
                    log.info(f"[Telemetry] → Bridge: {sentence}")

            elif self.format == 'json':
                message = self.format_as_json(data)
                self.sock.sendto(message.encode('utf-8'), (self.bridge_ip, self.bridge_port))
                log.info(f"[Telemetry] → Bridge: RPM={data['rpm']}, Ballast={data['ballast']}, Pump={data['pump_status']}")

        except Exception as e:
            log.error(f"[Telemetry Sender] Send error: {e}")

    def run(self, interval=2):
        """메인 루프"""
        if not self.connect_plc():
            log.error("[Telemetry Sender] Cannot start without PLC connection")
            return

        log.info(f"[Telemetry Sender] Sending to {self.bridge_ip}:{self.bridge_port} (format: {self.format})")
        log.info(f"[Telemetry Sender] Update interval: {interval} seconds")

        try:
            while True:
                data = self.read_plc_data()
                if data:
                    self.send_to_bridge(data)
                time.sleep(interval)

        except KeyboardInterrupt:
            log.info("\n[Telemetry Sender] Shutting down...")
        finally:
            if self.client:
                self.client.close()
            self.sock.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Engine Telemetry Sender')
    parser.add_argument('--plc-host', default='localhost', help='PLC server host')
    parser.add_argument('--plc-port', type=int, default=502, help='PLC server port')
    parser.add_argument('--bridge-ip', default='10.10.10.10', help='Bridge Zone IP')
    parser.add_argument('--bridge-port', type=int, default=10113, help='Bridge Zone port')
    parser.add_argument('--format', choices=['nmea', 'json'], default='nmea', help='Output format')
    parser.add_argument('--interval', type=int, default=2, help='Update interval (seconds)')

    args = parser.parse_args()

    sender = EngineTelemetrySender(
        plc_host=args.plc_host,
        plc_port=args.plc_port,
        bridge_ip=args.bridge_ip,
        bridge_port=args.bridge_port,
        format=args.format
    )

    sender.run(interval=args.interval)
