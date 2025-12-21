# 선박 OT 공격 시나리오 분석 및 안전성 기반 자동 대응 플레이북 개발

## 프로젝트 개요
선박 OT(Operational Technology) 시스템에 대한 사이버 공격 시뮬레이션 및 자동 대응 시스템

## 스크립트 목록

### Field Zone (라즈베리파이) - 4개
1. **gps_sim.py** - GPS 시뮬레이터
   - NMEA 형식의 GPS 데이터 생성 및 전송
   - 선박 위치, 속도, 방향 시뮬레이션

2. **ais_sim.py** - AIS 시뮬레이터
   - 선박 자동 식별 시스템 데이터 생성
   - Position Report 및 Static Data 전송

3. **sensor_sim.py** - 센서 시뮬레이터
   - 엔진, 연료, 냉각, 전기 시스템 센서 데이터
   - 알람 및 경고 시스템

4. **nmea_multiplexer.py** - NMEA 멀티플렉서
   - 여러 소스의 데이터를 수집하고 통합
   - 클라이언트에 재전송

### Control Zone (VM) - 5개
5. **plc_server.py** - PLC 서버
   - Modbus TCP 서버
   - 엔진 제어 시스템

6. **engine_logic.py** - 엔진 로직 제어기
   - PLC와 연동하여 엔진 상태 관리
   - RPM, Ballast, Pump 상태 시뮬레이션

7. **engine_telemetry_sender.py** - 엔진 텔레메트리 전송기
   - PLC 데이터를 Bridge Zone으로 전송
   - NMEA XDR 또는 JSON 형식 지원
   - Control Zone → Bridge Zone 연결

8. **hmi_bridge.py** - HMI 브릿지
   - PLC 데이터를 HTTP REST API로 노출
   - 웹 기반 모니터링 인터페이스 제공

9. **sensor_to_plc.py** - 센서 데이터 연결기
   - Field Zone Sensor 데이터를 PLC로 전송
   - UDP → Modbus 변환
   - 센서 값을 PLC 레지스터에 매핑

### Attacker - 1개
10. **modbus_attacker.py** - Modbus PLC 공격 시뮬레이터
    - PLC에 대한 다양한 공격 패턴 시뮬레이션
    - 4가지 공격 모드: force_fill, force_drain, oscillate, stealthy
    - RPM, Ballast, PumpMode 변조 (Node-RED에 즉시 반영)
    - 교육 및 테스트 목적 전용

## 필요한 Python 패키지

```bash
# pymodbus 2.5.3 사용 (안정적인 버전, 권장)
pip install pymodbus==2.5.3

# 또는 pymodbus 3.x (modbus_attacker.py는 3.x도 지원)
pip install pymodbus

# 추가 패키지
pip install prometheus-client
```

**중요**:
- **Control Zone 스크립트들**: pymodbus 2.5.3 사용 (안정적)
- **modbus_attacker.py**: pymodbus 2.5.3 및 3.x 모두 지원

## 실행 방법

### Field Zone 실행
```bash
# 각각 별도 터미널에서 실행
python gps_sim.py
python ais_sim.py
python sensor_sim.py
python nmea_multiplexer.py
```

### Control Zone 실행
```bash
# 1. PLC 서버 시작 (각각 별도 터미널)
cd control
python plc_server.py

# 2. 엔진 로직 시작 (PLC에 데이터 쓰기)
python engine_logic.py

# 3. 엔진 텔레메트리 전송 (PLC → Bridge Zone)
python engine_telemetry_sender.py --bridge-ip 10.10.10.10 --format nmea

# 4. HMI 브릿지 시작
python hmi_bridge.py --http-port 8080

# 5. 센서 데이터 연결 (Field → Control)
python sensor_to_plc.py --sensor-port 10112

# HMI 대시보드 접속
# http://localhost:8080/
```

## 포트 정보

### Field Zone
- GPS Simulator: 10110
- AIS Simulator: 10111
- Sensor Simulator: 10112
- NMEA Multiplexer: 10113

### Control Zone
- PLC Server (Modbus TCP): 502
- HMI Bridge (HTTP API): 8080
- Engine Telemetry Sender → Bridge: 10113

### Bridge Zone
- OpenCPN NMEA Input: 10110
- Engine Telemetry Input: 10113

## 주의사항
⚠️ **경고**: 이 스크립트들은 교육 및 테스트 목적으로만 사용해야 합니다.
- 허가받은 시스템에서만 사용하세요
- 실제 운영 환경에서 사용하지 마세요
- 공격 시뮬레이션은 격리된 네트워크에서만 실행하세요

## 프로젝트 구조
```
coke/
├── field/                          # Field Zone (라즈베리파이)
│   ├── gps_sim.py
│   ├── ais_sim.py
│   ├── sensor_sim.py
│   └── nmea_multiplexer.py
│
├── control/                        # Control Zone (VM)
│   ├── plc_server.py
│   ├── engine_logic.py
│   ├── engine_telemetry_sender.py
│   ├── hmi_bridge.py
│   └── sensor_to_plc.py
│
├── attacker/                       # Attack Scripts
│   └── modbus_attacker.py
│
└── README.md
```

## 주요 기능

### 1️⃣ Control Zone → Bridge Zone 데이터 전송
`engine_telemetry_sender.py`로 구현
- PLC Modbus 데이터를 주기적으로 읽기
- NMEA XDR 형식 또는 JSON으로 변환
- Bridge Zone (10.10.10.10:10113)으로 UDP 전송
- OpenCPN에서 엔진 상태 확인 가능

### 2️⃣ PLC ↔ HMI 연결
`hmi_bridge.py`로 구현
- HTTP REST API로 PLC 데이터 노출 (포트 8080)
- 웹 기반 대시보드 내장 (http://localhost:8080)
- 실시간 RPM/Ballast/Pump 모니터링
- 펌프 제어 버튼 제공

### 3️⃣ Sensor Simulator → PLC 연결
`sensor_to_plc.py`로 구현
- Field Zone의 센서 데이터를 UDP로 수신
- 엔진/연료/냉각/전기 데이터 파싱
- PLC Modbus 레지스터(10~18번)에 자동 매핑
- Control Zone이 실제 센서 값 기반으로 동작

## HMI Bridge API 사용법
```bash
# 전체 상태 조회
curl http://localhost:8080/api/plc/status

# RPM만 조회
curl http://localhost:8080/api/plc/rpm

# 펌프 토글
curl -X POST http://localhost:8080/api/plc/pump/toggle

# 레지스터 쓰기 (RPM 변경)
curl -X POST http://localhost:8080/api/plc/write_register \
  -H "Content-Type: application/json" \
  -d '{"address": 0, "value": 1500}'

# Coil 쓰기 (펌프 ON)
curl -X POST http://localhost:8080/api/plc/write_coil \
  -H "Content-Type: application/json" \
  -d '{"address": 0, "value": true}'
```

## Attacker 사용법

### Modbus PLC Attacker

PLC에 대한 다양한 공격 패턴을 시뮬레이션합니다.

```bash
cd attacker

# 기본 사용 (oscillate 모드, 60초)
python modbus_attacker.py --plc-ip localhost

# force_fill 모드로 30초 공격
python modbus_attacker.py --plc-ip localhost --mode force_fill --duration 30

# 빠른 공격 (0.5초 간격)
python modbus_attacker.py --plc-ip localhost --mode oscillate --interval 0.5

# 원격 PLC 공격
python modbus_attacker.py --plc-ip 10.10.40.10 --plc-port 502 --mode stealthy
```

### 공격 모드 설명

1. **force_fill**: Ballast를 40.0 근처로 고정 + FILL 모드 강제
   - 목적: 지속적인 물 주입 유도
   - 효과: 시스템이 계속 채우려고 시도

2. **force_drain**: Ballast를 50.0 근처로 고정 + DRAIN 모드 강제
   - 목적: 지속적인 물 배출 유도
   - 효과: 시스템이 계속 비우려고 시도

3. **oscillate** (권장): 40.0(FILL) ↔ 50.0(DRAIN) 빠르게 교체
   - 목적: 펌프 시스템 혼란 유발
   - 효과: 가장 눈에 띄는 비정상 동작

4. **stealthy**: 정상 범위(40~50) 내에서 무작위 값 + 무작위 펌프 모드
   - 목적: 탐지 회피하면서 시스템 교란
   - 효과: 정상처럼 보이지만 잘못된 제어 신호

### 옵션

- `--plc-ip`: PLC IP 주소 (기본: localhost)
- `--plc-port`: PLC Modbus 포트 (기본: 502)
- `--mode`: 공격 모드 (force_fill, force_drain, oscillate, stealthy)
- `--interval`: 쓰기 간격 (초, 기본: 1.5)
- `--duration`: 공격 지속 시간 (초, 기본: 60)

### 예상 출력

```
[INFO] [Attacker] Connected to PLC at localhost:502
[INFO] [Attacker] Starting Modbus Write Storm
[INFO]     Mode: oscillate
[INFO]     Interval: 1.5s
[INFO]     Duration: 60s
[INFO]
[INFO] [ATTACK] RPM=1234, Ballast=40.1, PumpMode=FILL(+1) (u16=1)
[INFO] [ATTACK] RPM=2567, Ballast=40.0, PumpMode=FILL(+1) (u16=1)
[INFO] [ATTACK] RPM=890,  Ballast=49.9, PumpMode=DRAIN(-1) (u16=65535)
...
[INFO]
[INFO] [Attacker] Attack finished
[INFO]     Elapsed: 60.2s
[INFO]     Writes attempted: 240
[INFO]     Writes successful: 240
[INFO]     Success rate: 100.0%
```

### Node-RED에서 관찰되는 변화

공격이 성공하면 Node-RED 대시보드에서:

- **RPM**: 0~3000 사이 무작위 값으로 계속 변화
- **Ballast**: oscillate 모드 시 40.0 ↔ 50.0 빠르게 왔다갔다
- **PumpMode**: FILL(1) ↔ DRAIN(-1) 계속 반복
- **그래프**: 지그재그 패턴 (정상은 완만한 곡선)

**주의**: engine_logic.py가 실행 중이면 공격 효과가 반감될 수 있으니 중지 권장
