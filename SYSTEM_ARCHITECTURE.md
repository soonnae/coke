# Ship Engine Monitoring System - System Architecture

## 1. 시스템 개요

본 시스템은 3-Zone 아키텍처로 구성된 선박 엔진 모니터링 및 제어 시스템입니다.
- **Field Zone**: 센서 데이터 수집
- **Control Zone**: 데이터 처리 및 제어 로직
- **Bridge Zone**: 모니터링 및 HMI (Human-Machine Interface)

---

## 2. 전체 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FIELD ZONE                                 │
│                      (Sensor Layer)                                 │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │         sensor_sim.py (Sensor Simulator)                  │     │
│  │  - 12개 센서 데이터 생성 (RPM, 온도, 압력, 연료 등)          │     │
│  │  - 2초 주기로 JSON 전송                                     │     │
│  └───────────────┬───────────────────────────┬───────────────┘     │
│                  │                           │                     │
│                  │ UDP:10112                 │ UDP:10113           │
│                  │ JSON                      │ JSON                │
└──────────────────┼───────────────────────────┼─────────────────────┘
                   │                           │
                   ↓                           │
┌─────────────────────────────────────────────┼─────────────────────┐
│              CONTROL ZONE                   │                     │
│          (Processing & Control)             │                     │
│  ┌──────────────────────────────┐           │                     │
│  │   sensor_to_plc.py           │           │                     │
│  │   - UDP 수신 (10112)         │           │                     │
│  │   - JSON → Modbus 변환        │           │                     │
│  │   - PLC HR[10-21] 쓰기        │           │                     │
│  └───────────┬──────────────────┘           │                     │
│              │                               │                     │
│              ↓                               │                     │
│  ┌──────────────────────────────────────┐   │                     │
│  │     PLC Server (plc_server.py)       │   │                     │
│  │     Modbus TCP Server (Port 502)     │   │                     │
│  │  ┌────────────────────────────────┐  │   │                     │
│  │  │  Holding Registers             │  │   │                     │
│  │  │  HR[1-2]:   제어 데이터         │  │   │                     │
│  │  │    - Ballast (x10)             │  │   │                     │
│  │  │    - Pump Mode                 │  │   │                     │
│  │  │  HR[10-21]: 센서 데이터         │  │   │                     │
│  │  │    - Engine (RPM, Temp, Oil...)│  │   │                     │
│  │  │    - Fuel, Cooling, Elec, Nav  │  │   │                     │
│  │  └────────────────────────────────┘  │   │                     │
│  └───────┬───────────────┬──────────────┘   │                     │
│          ↑               │                   │                     │
│          │               │                   │                     │
│  ┌───────┴──────┐        │                   │                     │
│  │ engine_      │        │                   │                     │
│  │ logic.py     │        │                   │                     │
│  │ - Ballast 생성│        │                   │                     │
│  │ - Pump 결정   │        │                   │                     │
│  │ - HR[1-2]쓰기 │        │                   │                     │
│  └──────────────┘        │                   │                     │
│                          │                   │                     │
│          ┌───────────────┴─────────┐         │                     │
│          │                         │         │                     │
│     ┌────┴─────────┐      ┌────────┴──────┐  │                     │
│     │ hmi_bridge.py│      │ engine_       │  │                     │
│     │              │      │ telemetry_    │  │                     │
│     │ - HR[1-21]   │      │ sender.py     │  │                     │
│     │   읽기        │      │               │  │                     │
│     │ - REST API   │      │ - HR[1-21]    │  │                     │
│     │   제공        │      │   읽기         │  │                     │
│     │ - Port 8080  │      │ - UDP 전송     │  │                     │
│     └────┬─────────┘      └────────┬──────┘  │                     │
│          │                         │         │                     │
│          │ HTTP                    │ UDP     │                     │
│          │ REST API                │ JSON    │                     │
└──────────┼─────────────────────────┼─────────┼─────────────────────┘
           │                         │         │
           ↓                         ↓         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         BRIDGE ZONE                                 │
│                    (Monitoring & HMI)                               │
│  ┌──────────────────────┐    ┌────────────────────────────────┐   │
│  │  Node-RED Dashboard  │    │  UDP Receiver System           │   │
│  │  http://localhost:   │    │  10.10.10.10:10113             │   │
│  │        1880/ui       │    │  - JSON 수신                    │   │
│  │  ┌────────────────┐  │    │  - 실시간 데이터 처리           │   │
│  │  │ RPM Gauge      │  │    └────────────────────────────────┘   │
│  │  │ Temp Gauge     │  │                                          │
│  │  │ Fuel Gauge     │  │    ┌────────────────────────────────┐   │
│  │  │ Ballast Gauge  │  │    │  External Systems              │   │
│  │  │ Pump Status    │  │    │  - curl / REST clients         │   │
│  │  └────────────────┘  │    │  - GET /api/plc/status         │   │
│  └──────────────────────┘    └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Zone별 상세 설명

### 3.1 Field Zone (센서 계층)

**역할**: 실시간 센서 데이터 수집 및 전송

#### 컴포넌트: sensor_sim.py

**기능**:
- 12개 센서 데이터 시뮬레이션
- 2초 주기로 데이터 생성
- JSON 형식으로 2곳에 동시 전송

**센서 데이터 목록**:

| 카테고리 | 센서 | 범위 | 단위 |
|---------|------|------|------|
| **Engine** | RPM | 600-1200 | RPM |
| | Temperature | 75-105 | °C |
| | Oil Pressure | 3.0-6.0 | bar |
| | Load | 30-95 | % |
| **Fuel** | Level | 10-100 | % |
| | Consumption Rate | 8-20 | L/h |
| | Temperature | - | °C |
| **Cooling** | Temperature | 70-95 | °C |
| | Pressure | 1.0-2.5 | bar |
| **Electrical** | Battery Voltage | 22-28 | V |
| **Navigation** | Rudder Angle | -35~+35 | ° |
| | Water Depth | 10-200 | m |

**전송 대상**:
1. Control Zone: `10.10.20.10:10112` (UDP)
2. Multiplexer: `127.0.0.1:10113` (UDP)

**데이터 형식**:
```json
{
  "timestamp": "2025-12-19T12:34:56.789",
  "engine": {
    "rpm": 850.0,
    "temperature": 85.0,
    "oil_pressure": 4.5,
    "load": 60.0
  },
  "fuel": {
    "level": 75.0,
    "consumption_rate": 12.5,
    "temperature": 35.0
  },
  "cooling": {
    "temperature": 82.0,
    "pressure": 1.8
  },
  "electrical": {
    "battery_voltage": 24.5
  },
  "navigation": {
    "rudder_angle": 0.0,
    "water_depth": 50.0
  },
  "alarms": []
}
```

---

### 3.2 Control Zone (처리 및 제어 계층)

**역할**: 데이터 처리, 저장, 제어 로직 실행, Bridge Zone으로 전달

#### 3.2.1 PLC Server (plc_server.py)

**기능**:
- Modbus TCP 서버 (Port 502)
- 중앙 데이터 저장소 역할
- 모든 컴포넌트가 읽기/쓰기

**PLC 레지스터 맵**:

| 주소 | 용도 | 데이터 | 스케일 | 설명 |
|------|------|--------|--------|------|
| **HR[0]** | (예약) | - | - | 미사용 |
| **HR[1]** | 제어 | Ballast | x10 | 40.0-50.0 → 400-500 |
| **HR[2]** | 제어 | Pump Mode | uint16 | -1(DRAIN), 0(HOLD), 1(FILL) |
| **HR[3-9]** | (예약) | - | - | 미사용 |
| **HR[10]** | 센서 | Engine RPM | x1 | 600-1200 RPM |
| **HR[11]** | 센서 | Engine Temperature | x1 | 75-105 °C |
| **HR[12]** | 센서 | Oil Pressure | x10 | 3.0-6.0 bar → 30-60 |
| **HR[13]** | 센서 | Engine Load | x1 | 30-95 % |
| **HR[14]** | 센서 | Fuel Level | x1 | 10-100 % |
| **HR[15]** | 센서 | Fuel Consumption | x10 | 8.0-20.0 L/h → 80-200 |
| **HR[16]** | 센서 | Fuel Temperature | x1 | °C |
| **HR[17]** | 센서 | Coolant Temperature | x1 | 70-95 °C |
| **HR[18]** | 센서 | Coolant Pressure | x10 | 1.0-2.5 bar → 10-25 |
| **HR[19]** | 센서 | Battery Voltage | x10 | 22-28 V → 220-280 |
| **HR[20]** | 센서 | Rudder Angle | +50 offset | -35~+35° → 15~85 |
| **HR[21]** | 센서 | Water Depth | x1 | 10-200 m |

#### 3.2.2 Sensor to PLC (sensor_to_plc.py)

**기능**:
- Field Zone UDP 데이터 수신 (Port 10112)
- JSON 파싱
- Modbus 레지스터 변환
- PLC HR[10-21] 쓰기

**처리 흐름**:
1. UDP 소켓에서 JSON 수신
2. 각 센서 값을 정수로 변환 (스케일링)
3. Modbus write_register() 호출
4. 성공/실패 로그 출력

**로그 출력**:
```
INFO:__main__:[Sensor→PLC] Engine: RPM=850, Temp=85°C, Oil=4.5bar, Load=60%
INFO:__main__:[Sensor→PLC] Fuel: Level=75%, Flow=12.5L/h, Temp=35°C
INFO:__main__:[Sensor→PLC] Cooling: Temp=82°C, Pressure=1.8bar
INFO:__main__:[Sensor→PLC] Electrical: Battery=24.5V
INFO:__main__:[Sensor→PLC] Navigation: Rudder=0°, Depth=50m
```

#### 3.2.3 Engine Logic (engine_logic.py)

**기능**:
- Ballast 레벨 시뮬레이션
- Pump Mode 결정 로직
- PLC HR[1-2] 쓰기

**제어 로직**:

**Ballast 생성**:
- 범위: 40.0 ~ 50.0
- 알고리즘: Random Walk
  - 이전 값 기준 ±3.0 범위에서 랜덤
  - 경계값 제한 (40.0, 50.0)
- 주기: 2초

**Pump Mode 결정**:
```python
if ballast <= 40.0:
    pump_mode = 1      # FILL (채우기)
elif ballast >= 50.0:
    pump_mode = -1     # DRAIN (배수)
else:
    pump_mode = 0      # HOLD (유지)
```

**로그 출력**:
```
INFO:__main__:[ControlLogic] Ballast=45.0→47.3, PumpMode=0 (HOLD)
INFO:__main__:[ControlLogic] Ballast=47.3→49.1, PumpMode=0 (HOLD)
INFO:__main__:[ControlLogic] Ballast=49.1→50.0, PumpMode=-1 (DRAIN)
```

#### 3.2.4 HMI Bridge (hmi_bridge.py)

**기능**:
- PLC 데이터 → REST API
- HTTP 서버 (Port 8080)
- 1초 주기로 PLC 읽기

**읽기 대상**:
- HR[1-2]: 제어 데이터 (Ballast, Pump)
- HR[10-21]: 센서 데이터 (12개)

**API 엔드포인트**:

**GET /api/plc/status**

응답 형식:
```json
{
  "engine": {
    "rpm": 850,
    "temperature": 85,
    "oil_pressure": 4.5,
    "load": 60
  },
  "fuel": {
    "level": 75,
    "consumption_rate": 12.5,
    "temperature": 35
  },
  "cooling": {
    "temperature": 82,
    "pressure": 1.8
  },
  "electrical": {
    "battery_voltage": 24.5
  },
  "navigation": {
    "rudder_angle": 0,
    "water_depth": 50
  },
  "control": {
    "ballast": 45.0,
    "pump_mode": 0
  },
  "connected": true,
  "last_update": 1734612345.678
}
```

#### 3.2.5 Engine Telemetry Sender (engine_telemetry_sender.py)

**기능**:
- PLC 데이터 → UDP 전송
- Bridge Zone으로 전송 (10.10.10.10:10113)
- 2초 주기

**읽기 대상**:
- HR[1-2]: 제어 데이터
- HR[10-21]: 센서 데이터

**전송 형식**: JSON (hmi_bridge와 동일)

**로그 출력**:
```
INFO:__main__:[Telemetry] → Bridge: Engine(RPM=850, Temp=85°C, Oil=4.5bar, Load=60%),
Fuel(Level=75%, Flow=12.5L/h, Temp=35°C), Cooling(Temp=82°C, Press=1.8bar),
Elec(Batt=24.5V), Nav(Rudder=0°, Depth=50m), Control(Ballast=45.0, Pump=0)
```

---

### 3.3 Bridge Zone (모니터링 계층)

**역할**: 실시간 모니터링 및 운영자 인터페이스

#### 3.3.1 Node-RED Dashboard

**접속**: http://localhost:1880/ui

**표시 게이지**:
1. **Engine RPM** - Gauge (0-2000 RPM)
2. **Engine Temperature** - Gauge (0-120°C)
3. **Fuel Level** - Donut Chart (0-100%)
4. **Ballast Level** - Donut Chart (40-50)
5. **Pump Mode** - Text (FILL/HOLD/DRAIN)
6. **Connection Status** - Text

**데이터 소스**: hmi_bridge.py REST API
**갱신 주기**: 2초

#### 3.3.2 UDP Receiver System

**수신 주소**: 10.10.10.10:10113
**프로토콜**: UDP JSON
**데이터 소스**: engine_telemetry_sender.py

---

## 4. 데이터 흐름

### 4.1 센서 데이터 흐름 (Field → Control → Bridge)

```
[sensor_sim.py]
    → UDP JSON (10112)
    → [sensor_to_plc.py]
    → Modbus Write
    → [PLC HR[10-21]]
    → Modbus Read
    → [hmi_bridge.py] → REST API → [Node-RED]
    → [engine_telemetry_sender.py] → UDP → [UDP Receiver]
```

**처리 시간**:
- sensor_sim.py 송신: 2초 주기
- sensor_to_plc.py 처리: 즉시
- PLC 저장: 즉시
- hmi_bridge.py 읽기: 1초 주기
- engine_telemetry_sender.py 읽기: 2초 주기

### 4.2 제어 데이터 흐름 (Control → Bridge)

```
[engine_logic.py]
    → Modbus Write
    → [PLC HR[1-2]]
    → Modbus Read
    → [hmi_bridge.py] → REST API → [Node-RED]
    → [engine_telemetry_sender.py] → UDP → [UDP Receiver]
```

**처리 시간**:
- engine_logic.py 생성: 2초 주기
- PLC 저장: 즉시
- 전송: 1-2초 주기

---

## 5. 통신 프로토콜

### 5.1 프로토콜 요약

| 구간 | 프로토콜 | 포트 | 형식 | 주기 |
|------|---------|------|------|------|
| Field → Control | UDP | 10112 | JSON | 2초 |
| Field → Multiplexer | UDP | 10113 | JSON | 2초 |
| Control (Internal) | Modbus TCP | 502 | Binary | 즉시 |
| Control → Bridge (REST) | HTTP | 8080 | JSON | 1초 |
| Control → Bridge (UDP) | UDP | 10113 | JSON | 2초 |

### 5.2 Modbus TCP

**서버**: plc_server.py (Port 502)
**클라이언트**:
- sensor_to_plc.py (Write)
- engine_logic.py (Write)
- hmi_bridge.py (Read)
- engine_telemetry_sender.py (Read)

**Function Codes**:
- FC03: Read Holding Registers
- FC06: Write Single Register

---

## 6. 시스템 실행 순서

### 6.1 시연 실행 절차

```bash
# 1단계 - Control Zone PLC 서버 시작 (필수)
터미널 1:
cd /home/user/coke/control
python plc_server.py
# 대기: [PLC] STATE-ONLY PLC started

# 2단계 - Field Zone 센서 시뮬레이터 시작 (필수)
터미널 2:
cd /home/user/coke/field
python sensor_sim.py
# 확인: 12개 센서 데이터 5줄 출력

# 3단계 - Field Zone → PLC 연결 (필수)
터미널 3:
cd /home/user/coke/control
python sensor_to_plc.py
# 확인: 센서 데이터 PLC 쓰기 로그 5줄 출력

# 4단계 - Control Zone 제어 로직 시작 (필수)
터미널 4:
cd /home/user/coke/control
python engine_logic.py
# 확인: Ballast, Pump 로그 출력

# 5단계 - Bridge Zone REST API (필수)
터미널 5:
cd /home/user/coke/control
python hmi_bridge.py
# 확인: [HMI Bridge] API http://localhost:8080/api/plc/status

# 6단계 - Bridge Zone UDP 전송 (필수)
터미널 6:
cd /home/user/coke/control
python engine_telemetry_sender.py
# 확인: 전체 데이터 전송 로그 출력

# 7단계 - Node-RED 대시보드 (선택)
터미널 7:
node-red
# 브라우저: http://localhost:1880/ui
```

### 6.2 동작 확인

**1. REST API 테스트**:
```bash
curl http://localhost:8080/api/plc/status | jq
```

**2. 로그 확인**:
- 터미널 2: 센서 생성 (5줄)
- 터미널 3: PLC 쓰기 (5줄)
- 터미널 4: 제어 로직 (1줄)
- 터미널 6: 전송 데이터 (1줄, 14개 값)

**3. 대시보드 확인**:
- http://localhost:1880/ui
- 6개 게이지 실시간 업데이트 확인

---

## 7. 시스템 특징

### 7.1 아키텍처 장점

1. **계층 분리**: 센서, 제어, 모니터링의 명확한 역할 분담
2. **확장성**: 각 Zone 독립적으로 확장 가능
3. **표준 프로토콜**: Modbus TCP, HTTP REST API, UDP
4. **실시간성**: 1-2초 주기 데이터 갱신
5. **다중 전송**: REST + UDP 동시 지원

### 7.2 데이터 무결성

- PLC를 중앙 저장소로 사용하여 데이터 일관성 보장
- Modbus TCP 프로토콜의 신뢰성
- 에러 핸들링 및 재연결 로직

### 7.3 모니터링 기능

- 실시간 센서 데이터 (12개)
- 제어 상태 (Ballast, Pump)
- 연결 상태 표시
- 시각화 (게이지, 차트)

---

## 8. 기술 스택

| 계층 | 기술 |
|------|------|
| **Language** | Python 3.x |
| **PLC Protocol** | Modbus TCP (pymodbus) |
| **Network** | UDP, HTTP |
| **Data Format** | JSON |
| **Web Server** | Python http.server |
| **Dashboard** | Node-RED |
| **Logging** | Python logging module |

---

## 9. 파일 구조

```
/home/user/coke/
├── field/
│   └── sensor_sim.py              # Field Zone 센서 시뮬레이터
├── control/
│   ├── plc_server.py              # PLC Modbus TCP 서버
│   ├── sensor_to_plc.py           # Field → PLC 연결
│   ├── engine_logic.py            # 제어 로직 (Ballast, Pump)
│   ├── hmi_bridge.py              # PLC → REST API
│   ├── engine_telemetry_sender.py # PLC → UDP
│   └── node-red-flow.json         # Node-RED 설정
└── bridge/
    └── (외부 시스템: Node-RED, UDP Receiver)
```

---

## 10. 향후 개선 방향

1. **데이터베이스 연동**: 이력 데이터 저장 (InfluxDB, PostgreSQL)
2. **알람 시스템**: 임계값 기반 알람 발생 및 전송
3. **제어 명령**: Bridge → Control 양방향 통신
4. **보안**: TLS/SSL, 인증, 접근 제어
5. **HA (High Availability)**: PLC 이중화, 장애 복구
6. **성능 최적화**: 배치 처리, 캐싱
7. **모바일 앱**: 스마트폰 모니터링

---

## 문서 버전

- **작성일**: 2025-12-19
- **버전**: 1.0
- **작성자**: System Architect
- **시스템**: Ship Engine Monitoring System
