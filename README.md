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

### Attacker VM - 3개
8. **arp_mitm_attack.py** - ARP MITM 공격 ⭐ NEW
   - Layer 2 네트워크 공격
   - Field ↔ Bridge 간 통신 경로 탈취
   - 공격 모드: Black Hole, Delay, Forward, Sniff
   - 데이터가 아닌 "통신 경로 자체" 공격

9. **modbus_flood.py** - Modbus 플러딩 공격
   - Modbus TCP 프로토콜 플러딩 공격
   - 다중 스레드 공격 시뮬레이션

10. **sensor_replay.py** - 센서 재전송 공격
    - Man-in-the-Middle 공격
    - 패킷 캡처 및 재생

### 옵션 - 2개
11. **gps_jump_attack.py** - GPS 점프 공격
    - GPS 좌표 급격한 변경 공격
    - 랜덤 점프, 고정 위치, 드리프트 모드

12. **coil_single_attack.py** - Coil 제어 공격
    - Modbus Coil 단일 제어 공격
    - 비상 정지, 엔진 정지, 빠른 토글 공격

## 필요한 Python 패키지

```bash
pip install pymodbus prometheus-client scapy netifaces
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

#### ARP MITM 공격 (Network Layer - L2) ⭐ NEW
```bash
# Black Hole 모드 - 통신 완전 차단
sudo python3 attacker/arp_mitm_attack.py \
  --target1 10.10.20.10 \
  --target2 10.10.10.10 \
  --mode blackhole

# Delay 모드 - 패킷 2초 지연
sudo python3 attacker/arp_mitm_attack.py \
  --target1 10.10.20.10 \
  --target2 10.10.10.10 \
  --mode delay \
  --delay 2.0

# Sniff 모드 - NMEA 데이터 캡처
sudo python3 attacker/arp_mitm_attack.py \
  --target1 10.10.20.10 \
  --target2 10.10.10.10 \
  --mode sniff

# Forward 모드 - 탐지 테스트 (정상 전달)
sudo python3 attacker/arp_mitm_attack.py \
  --target1 10.10.20.10 \
  --target2 10.10.10.10 \
  --mode forward
```

**공격 효과:**
- **Black Hole**: OpenCPN이 "No GPS Data" / "AIS Lost" 표시
- **Delay**: 항해 정보가 2초 늦게 반영 → 항해 판단 불가능
- **Sniff**: 모든 NMEA 데이터 캡처 (정보 수집)

**차별점:**
- 기존 공격(1~6번): 데이터 내용 조작 (Application Layer)
- ARP MITM: 통신 경로 자체 공격 (Data Link Layer)

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
│   ├── ais_sim.py
│   ├── sensor_sim.py
│   └── nmea_multiplexer.py
├── control/
│   ├── plc_server.py
│   ├── engine_logic.py
│   └── plc_exporter.py
├── attacker/
│   ├── arp_mitm_attack.py        ⭐ NEW
│   ├── modbus_flood.py
│   ├── sensor_replay.py
│   ├── gps_jump_attack.py
│   └── coil_single_attack.py
└── README.md
```

## 공격 시나리오 매핑 (A, B, C Zone)

| 시나리오 | 공격 유형 | 주도 Zone | 공격 스크립트 |
|---|---|---|---|
| ① NMEA Data Spoofing | GPS/AIS 위조 | A & C | `gps_jump_attack.py` |
| ② Modbus Write Flood | PLC 파라미터 공격 | C & B | `modbus_flood.py` |
| ③ **ARP MITM** ⭐ | **통신 경로 탈취** | **A & B** | `arp_mitm_attack.py` |
| ④ HMI UI 조작 | Dashboard 왜곡 | A | (Node-RED 직접 접근) |
| ⑤ Single Modbus Coil | 부분 제어 교란 | C | `coil_single_attack.py` |
| ⑥ Sensor Replay | 센서값 리플레이 | C & B | `sensor_replay.py` |

**시나리오 3 (ARP MITM)의 차별점:**
- 유일한 **Layer 2 공격** (나머지는 모두 Layer 7)
- 데이터가 아닌 **네트워크 경로 자체** 공격
- Integration Zone(B)의 **ARP 탐지 능력** 시연에 핵심적
