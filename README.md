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

### Control Zone (VM) - 3개
5. **plc_server.py** - PLC 서버
   - Modbus TCP 서버
   - 엔진 제어 시스템

6. **engine_logic.py** - 엔진 로직 제어기
   - PLC와 연동하여 엔진 상태 관리
   - 안전 체크 및 자동 제어

7. **plc_exporter.py** - PLC Exporter
   - Prometheus 형식으로 메트릭 내보내기
   - 모니터링 및 시각화 지원

### Attacker VM (담당자 C) - 2개
8. **modbus_flood.py** - Modbus 플러딩 공격
   - Modbus TCP 프로토콜 플러딩 공격
   - 다중 스레드 공격 시뮬레이션

9. **sensor_replay.py** - 센서 재전송 공격
   - Man-in-the-Middle 공격
   - 패킷 캡처 및 재생

### Initialization Poisoning (시나리오 3) - 2개 ⭐
10. **gps_sim_poisoned.py** - GPS 초기화 오염
    - 시작 시점부터 잘못된 위치 (~1km offset)
    - 이후 모든 항적이 오염된 기준점 기반 계산
    - Boot phase vulnerability 시연

11. **plc_server_poisoned.py** - PLC 초기화 오염
    - 시작 시점부터 잘못된 레지스터 값 (RPM -50, Ballast -5)
    - 모든 제어 로직이 틀린 baseline 기반 동작
    - Configuration integrity 시연

### 옵션 - 2개
12. **gps_jump_attack.py** - GPS 점프 공격
    - GPS 좌표 급격한 변경 공격
    - 랜덤 점프, 고정 위치, 드리프트 모드

13. **coil_single_attack.py** - Coil 제어 공격
    - Modbus Coil 단일 제어 공격
    - 비상 정지, 엔진 정지, 빠른 토글 공격

## 필요한 Python 패키지

```bash
pip install pymodbus prometheus-client
```

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
# PLC 서버 시작 (관리자 권한 필요할 수 있음)
python plc_server.py

# 엔진 로직 시작
python engine_logic.py

# Exporter 시작
python plc_exporter.py
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

#### Coil 제어 공격 (시나리오 5) ⭐
```bash
# 비상 정지 공격 (Pump OFF 강제)
python3 attacker/coil_single_attack.py --host localhost --attack emergency_stop

# Pump 토글 공격 (ON/OFF 반복, 60초, 5초 간격)
python3 attacker/coil_single_attack.py --host localhost --attack pump_toggle --duration 60 --interval 5

# 빠른 토글 공격 (하드웨어 손상 유도, 30초, 0.5초 간격)
python3 attacker/coil_single_attack.py --host localhost --attack rapid_toggle --duration 30 --interval 0.5

# 복구 (Pump ON으로 복원)
python3 attacker/coil_single_attack.py --host localhost --attack restore
```

**공격 효과:**
- **emergency_stop**: Pump Coil을 OFF로 강제 → HMI에서 펌프 정지 표시
- **pump_toggle**: 주기적 ON/OFF → 시스템 불안정, IDS 탐지
- **rapid_toggle**: 빠른 ON/OFF 반복 → 하드웨어 스트레스, "repeated coil write" 탐지
- **restore**: 정상 상태(ON)로 복구

**Zone 역할:**
- **C (Control)**: PLC 영향 시연, 제어 교란 확인
- **B (Integration)**: Suricata "repeated coil write" rule 탐지 → 공격자 차단
- **A (Bridge)**: HMI에서 Pump 상태 이상 시각화

#### Initialization Poisoning (시나리오 3) ⭐ NEW
```bash
# 방법 1: GPS 초기화 오염 시연
# 정상 GPS 대신 오염된 버전 실행
python3 field/gps_sim_poisoned.py

# 방법 2: PLC 초기화 오염 시연
# 정상 PLC 대신 오염된 버전 실행
python3 control/plc_server_poisoned.py

# 방법 3: 비교 시연 (권장)
# 1) 먼저 정상 버전 실행 → OpenCPN/HMI 확인
# 2) 중지 후 오염 버전 실행 → 차이 관찰
```

**공격 효과:**
- **GPS Poisoned**:
  - 시작 시점부터 위치 ~1km offset
  - 이후 모든 항적이 틀린 기준점 기반 계산
  - OpenCPN에서 "왜 계속 위치가 이상하지?" 관찰

- **PLC Poisoned**:
  - 시작 시점부터 RPM -50, Ballast -5
  - Engine Logic이 틀린 baseline 기반 동작
  - HMI가 틀린 값을 "정상"으로 표시

**차별점:**
- 기존 시나리오: 운영 중 실시간 공격
- **이 시나리오: 시작 단계 1회 오염 → 지속적 영향**
- 탐지: Baseline deviation (초기 설정 무결성 검증)

**Zone 역할:**
- **C (Field/Control)**: 오염된 초기값으로 시작
- **B (Integration)**: "Baseline deviation from known-good" 탐지
- **A (Bridge)**: 미세하게 계속 어긋나는 현상 시각화

**실제 사고 맥락:**
- 선박 기동 시 GPS 초기 Fix 오류
- PLC Firmware 업데이트 후 잘못된 기본값
- Configuration file 변조 (Supply chain attack)

## 포트 정보
- GPS Simulator: 10110
- AIS Simulator: 10111
- Sensor Simulator: 10112
- NMEA Multiplexer: 10113
- PLC Server (Modbus): 502
- PLC Exporter (Prometheus): 9100
- Sensor Replay Proxy: 10212
- GPS Jump Proxy: 10210

## 주의사항
⚠️ **경고**: 이 스크립트들은 교육 및 테스트 목적으로만 사용해야 합니다.
- 허가받은 시스템에서만 사용하세요
- 실제 운영 환경에서 사용하지 마세요
- 공격 시뮬레이션은 격리된 네트워크에서만 실행하세요

## 프로젝트 구조
```
CokE/
├── field/
│   ├── gps_sim.py
│   ├── gps_sim_poisoned.py      ⭐ NEW (Scenario 3)
│   ├── ais_sim.py
│   ├── sensor_sim.py
│   └── nmea_multiplexer.py
├── control/
│   ├── plc_server.py
│   ├── plc_server_poisoned.py   ⭐ NEW (Scenario 3)
│   ├── engine_logic.py
│   └── plc_exporter.py
├── attacker/
│   ├── coil_single_attack.py    ⭐ NEW (Scenario 5)
│   ├── modbus_flood.py
│   ├── sensor_replay.py
│   └── gps_jump_attack.py
└── README.md
```

## 담당자 C 역할
- **필수**: `modbus_flood.py`, `sensor_replay.py`
- **옵션**: `gps_jump_attack.py`, `coil_single_attack.py`
