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

### Control Zone (VM) - 6개
5. **plc_server.py** - PLC 서버
   - Modbus TCP 서버
   - 엔진 제어 시스템

6. **engine_logic.py** - 엔진 로직 제어기
   - PLC와 연동하여 엔진 상태 관리
   - RPM, Ballast, Pump 상태 시뮬레이션

7. **engine_telemetry_sender.py** - 엔진 텔레메트리 전송기 ⭐ NEW
   - PLC 데이터를 Bridge Zone으로 전송
   - NMEA XDR 또는 JSON 형식 지원
   - Control Zone → Bridge Zone 연결

8. **hmi_bridge.py** - HMI 브릿지 (Node-RED 연동) ⭐ NEW
   - PLC 데이터를 HTTP REST API로 노출
   - Node-RED HMI 대시보드 연동
   - 웹 기반 모니터링 인터페이스 제공

9. **sensor_to_plc.py** - 센서 데이터 연결기 ⭐ NEW
   - Field Zone Sensor 데이터를 PLC로 전송
   - UDP → Modbus 변환
   - 센서 값을 PLC 레지스터에 매핑

10. **node-red-flow.json** - Node-RED 설정 파일 ⭐ NEW
    - HMI 대시보드 Flow 설정
    - RPM, Ballast, Pump 게이지
    - 펌프 제어 버튼

### Attacker VM (담당자 C) - 2개
11. **modbus_flood.py** - Modbus 플러딩 공격 (TODO)
    - Modbus TCP 프로토콜 플러딩 공격
    - 다중 스레드 공격 시뮬레이션

12. **sensor_replay.py** - 센서 재전송 공격 (TODO)
    - Man-in-the-Middle 공격
    - 패킷 캡처 및 재생

### 옵션 - 2개
13. **gps_jump_attack.py** - GPS 점프 공격 (TODO)
    - GPS 좌표 급격한 변경 공격
    - 랜덤 점프, 고정 위치, 드리프트 모드

14. **coil_single_attack.py** - Coil 제어 공격 (TODO)
    - Modbus Coil 단일 제어 공격
    - 비상 정지, 엔진 정지, 빠른 토글 공격

## 필요한 Python 패키지

```bash
# pymodbus 3.x 사용 (3.0.0 이상)
pip install pymodbus>=3.0.0

# 추가 패키지
pip install prometheus-client
```

**중요**: 이 프로젝트는 pymodbus 3.x를 사용합니다. 2.x와 API가 다르니 주의하세요!

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

# 3. 엔진 텔레메트리 전송 (PLC → Bridge Zone) ⭐ NEW
python engine_telemetry_sender.py --bridge-ip 10.10.10.10 --format nmea

# 4. HMI 브릿지 시작 (Node-RED 연동) ⭐ NEW
python hmi_bridge.py --http-port 8080

# 5. 센서 데이터 연결 (Field → Control) ⭐ NEW
python sensor_to_plc.py --sensor-port 10112

# HMI 대시보드 접속
# http://localhost:8080/  (간단한 웹 대시보드)
# http://localhost:1880/ui  (Node-RED 대시보드 - Node-RED 설치 필요)
```

### 공격 시뮬레이션

#### Modbus 플러딩 공격
```bash
python modbus_flood.py --host localhost --port 502 --intensity high --duration 60
```

#### 센서 재전송 공격
```bash
# 캡처 모드
python sensor_replay.py --sensor-host localhost --sensor-port 10112 --proxy-port 10212

# 재생 모드
python sensor_replay.py --replay --replay-speed 2.0 --load captured_data.json
```

#### GPS 점프 공격 (옵션)
```bash
python gps_jump_attack.py --attack random_jump --distance 10 --frequency 5
```

#### Coil 제어 공격 (옵션)
```bash
# 비상 정지 공격
python coil_single_attack.py --attack emergency_stop

# 엔진 정지 공격
python coil_single_attack.py --attack engine_shutdown

# 복구
python coil_single_attack.py --attack restore
```

## 포트 정보

### Field Zone
- GPS Simulator: 10110
- AIS Simulator: 10111
- Sensor Simulator: 10112
- NMEA Multiplexer: 10113

### Control Zone
- PLC Server (Modbus TCP): 502
- HMI Bridge (HTTP API): 8080 ⭐ NEW
- Engine Telemetry Sender → Bridge: 10113 ⭐ NEW

### Bridge Zone
- OpenCPN NMEA Input: 10110
- Engine Telemetry Input: 10113 ⭐ NEW

### Attack Scripts
- Sensor Replay Proxy: 10212 (TODO)
- GPS Jump Proxy: 10210 (TODO)

### HMI/Monitoring
- Node-RED Dashboard: 1880
- HMI Web Dashboard: 8080 ⭐ NEW

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
│   ├── engine_telemetry_sender.py  ⭐ NEW
│   ├── hmi_bridge.py               ⭐ NEW
│   ├── sensor_to_plc.py            ⭐ NEW
│   └── node-red-flow.json          ⭐ NEW
│
├── attack/                         # Attack Scripts (TODO)
│   ├── modbus_flood.py             (TODO)
│   ├── sensor_replay.py            (TODO)
│   ├── gps_jump_attack.py          (TODO)
│   └── coil_single_attack.py       (TODO)
│
└── README.md
```

## 담당자 C 역할
- **Control Zone + Field Zone 책임자**
- **필수 공격 스크립트**: `modbus_flood.py`, `sensor_replay.py` (TODO)
- **옵션 공격 스크립트**: `gps_jump_attack.py`, `coil_single_attack.py` (TODO)
- **완료된 통합 스크립트**: ✅
  - `engine_telemetry_sender.py` - Control → Bridge 연결
  - `hmi_bridge.py` - PLC ↔ Node-RED HMI
  - `sensor_to_plc.py` - Field Sensor → Control PLC
  - `node-red-flow.json` - HMI 대시보드 설정

---

## 🆕 새로운 기능 (Control Zone 통합 완료)

### 1️⃣ Control Zone → Bridge Zone 데이터 전송
**문제**: Control Zone의 엔진 데이터가 Bridge Zone으로 전달되지 않았음
**해결**: `engine_telemetry_sender.py` 추가
- PLC Modbus 데이터를 주기적으로 읽기
- NMEA XDR 형식 또는 JSON으로 변환
- Bridge Zone (10.10.10.10:10113)으로 UDP 전송
- OpenCPN에서 엔진 상태 확인 가능

### 2️⃣ PLC ↔ HMI (Node-RED) 연결
**문제**: HMI 인터페이스가 없었음
**해결**: `hmi_bridge.py` + `node-red-flow.json` 추가
- HTTP REST API로 PLC 데이터 노출 (포트 8080)
- 웹 기반 대시보드 내장 (http://localhost:8080)
- Node-RED와 연동 가능
- 실시간 RPM/Ballast/Pump 모니터링
- 펌프 제어 버튼 제공

### 3️⃣ Sensor Simulator → PLC 연결
**문제**: Sensor 데이터가 받기만 하고 사용되지 않았음
**해결**: `sensor_to_plc.py` 추가
- Field Zone의 센서 데이터를 UDP로 수신
- 엔진/연료/냉각/전기 데이터 파싱
- PLC Modbus 레지스터(10~18번)에 자동 매핑
- Control Zone이 실제 센서 값 기반으로 동작

---

## Node-RED 설치 및 설정 (선택)

### Node-RED 설치
```bash
# Node.js 설치 (필요시)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Node-RED 설치
sudo npm install -g --unsafe-perm node-red

# Dashboard 모듈 설치
cd ~/.node-red
npm install node-red-dashboard
```

### Node-RED 시작 및 설정
```bash
# Node-RED 실행
node-red

# 브라우저에서 열기
# http://localhost:1880

# Flow 가져오기
# 1. Menu → Import → Clipboard
# 2. control/node-red-flow.json 내용 복사/붙여넣기
# 3. Deploy 클릭

# 대시보드 접속
# http://localhost:1880/ui
```

### HMI Bridge API 사용법
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
