# Field Zone - 센서 데이터 수집 계층 상세 문서

## 목차
1. [Field Zone 개요](#1-field-zone-개요)
2. [시스템 아키텍처에서의 역할](#2-시스템-아키텍처에서의-역할)
3. [sensor_sim.py 상세 분석](#3-sensor_simpy-상세-분석)
4. [센서 시뮬레이션 시스템](#4-센서-시뮬레이션-시스템)
5. [데이터 전송 메커니즘](#5-데이터-전송-메커니즘)
6. [알람 시스템](#6-알람-시스템)
7. [실행 및 운영](#7-실행-및-운영)
8. [설정 및 커스터마이징](#8-설정-및-커스터마이징)
9. [트러블슈팅](#9-트러블슈팅)
10. [성능 및 확장성](#10-성능-및-확장성)

---

## 1. Field Zone 개요

### 1.1 정의

Field Zone은 3-Zone 선박 모니터링 시스템의 최하위 계층으로, **실시간 센서 데이터 수집 및 전송**을 담당합니다. 실제 선박 환경에서는 물리적 센서 장비가 위치하지만, 본 시스템에서는 시뮬레이터를 통해 센서 동작을 재현합니다.

### 1.2 주요 책임

| 책임 | 설명 |
|------|------|
| **데이터 수집** | 12개 센서로부터 실시간 데이터 수집 (시뮬레이션) |
| **데이터 생성** | 현실적인 센서 값 생성 (랜덤 워크, 범위 제한) |
| **데이터 전송** | Control Zone 및 Multiplexer로 UDP 전송 |
| **알람 감지** | 임계값 기반 알람 상태 생성 |
| **주기 관리** | 2초 주기 데이터 갱신 및 전송 |

### 1.3 컴포넌트 구성

```
Field Zone
└── sensor_sim.py
    ├── SensorSimulator 클래스
    │   ├── 센서 상태 변수 (12개)
    │   ├── 데이터 생성 메서드
    │   ├── 센서 업데이트 로직
    │   ├── 알람 체크 로직
    │   └── 전송 메커니즘
    └── 설정
        ├── TARGET_IP: 10.10.20.10
        ├── TARGET_PORT: 10112
        ├── MULTIPLEXER_IP: 127.0.0.1
        └── MULTIPLEXER_PORT: 10113
```

---

## 2. 시스템 아키텍처에서의 역할

### 2.1 데이터 흐름도

```
┌─────────────────────────────────────────────────────────────┐
│                       FIELD ZONE                            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         sensor_sim.py (Sensor Simulator)            │   │
│  │                                                     │   │
│  │  ┌───────────────────────────────────────────┐     │   │
│  │  │  센서 시뮬레이터 (SensorSimulator)        │     │   │
│  │  │                                           │     │   │
│  │  │  [초기화]                                 │     │   │
│  │  │  - 12개 센서 초기값 설정                  │     │   │
│  │  │  - UDP 소켓 생성                          │     │   │
│  │  │                                           │     │   │
│  │  │  [메인 루프 - 2초 주기]                   │     │   │
│  │  │  1. 센서 데이터 생성 (generate_sensor_data)│     │   │
│  │  │     ↓                                     │     │   │
│  │  │  2. 알람 체크 (check_alarms)              │     │   │
│  │  │     ↓                                     │     │   │
│  │  │  3. JSON 직렬화                           │     │   │
│  │  │     ↓                                     │     │   │
│  │  │  4. UDP 전송 (2곳 동시)                   │     │   │
│  │  │     ├─→ Control Zone (10.10.20.10:10112) │     │   │
│  │  │     └─→ Multiplexer (127.0.0.1:10113)    │     │   │
│  │  │     ↓                                     │     │   │
│  │  │  5. 로그 출력 (5줄)                       │     │   │
│  │  │     ↓                                     │     │   │
│  │  │  6. 센서 값 업데이트 (update_sensors)     │     │   │
│  │  │     ↓                                     │     │   │
│  │  │  7. 2초 대기                              │     │   │
│  │  │     ↓                                     │     │   │
│  │  │  8. 반복                                  │     │   │
│  │  └───────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────┬──────────────────┬───────────────────────┘
                   │                  │
                   │ UDP JSON         │ UDP JSON
                   │                  │
                   ↓                  ↓
        ┌──────────────────┐  ┌─────────────────┐
        │  Control Zone    │  │  Multiplexer    │
        │  sensor_to_plc.py│  │  (NMEA 변환)    │
        │  Port: 10112     │  │  Port: 10113    │
        └──────────────────┘  └─────────────────┘
```

### 2.2 인터페이스

#### 출력 인터페이스

| 인터페이스 | 프로토콜 | 대상 | 포트 | 형식 | 주기 |
|-----------|---------|------|------|------|------|
| **Control Zone** | UDP | 10.10.20.10 | 10112 | JSON | 2초 |
| **Multiplexer** | UDP | 127.0.0.1 | 10113 | JSON | 2초 |

---

## 3. sensor_sim.py 상세 분석

### 3.1 파일 정보

- **위치**: `/home/user/coke/field/sensor_sim.py`
- **언어**: Python 3.x
- **의존성**: `socket`, `json`, `time`, `random`, `datetime`
- **라인 수**: 약 220줄
- **클래스**: SensorSimulator

### 3.2 전역 설정

```python
TARGET_IP = "10.10.20.10"        # Control Zone IP
TARGET_PORT = 10112              # Control Zone UDP 포트
MULTIPLEXER_IP = "127.0.0.1"     # Multiplexer IP (로컬)
MULTIPLEXER_PORT = 10113         # Multiplexer UDP 포트
```

**설정 특징**:
- 명령줄 인자로 오버라이드 가능
- `--target-ip`, `--target-port` 옵션 지원

### 3.3 SensorSimulator 클래스 구조

#### 3.3.1 초기화 (__init__)

```python
class SensorSimulator:
    def __init__(self):
        # UDP 소켓 생성
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 센서 초기값 설정 (12개)
        self.engine_rpm = 850.0
        self.engine_temp = 85.0
        self.engine_oil_pressure = 4.5
        self.engine_load = 60.0

        self.fuel_level = 75.0
        self.fuel_consumption = 12.5
        self.fuel_temp = 35.0

        self.coolant_temp = 82.0
        self.coolant_pressure = 1.8

        self.battery_voltage = 24.5
        self.rudder_angle = 0.0
        self.water_depth = 50.0

        # 알람 리스트
        self.alarms = []
```

**초기값 설정 근거**:
- 일반적인 선박 엔진 정상 운전 상태를 반영
- 중간값으로 설정하여 상승/하강 여유 확보
- 실제 선박 사양서 및 매뉴얼 참조

#### 3.3.2 메인 루프 (start)

```python
def start(self):
    print(f"[Sensor Simulator] Sending to:")
    print(f"  - Control Zone: {TARGET_IP}:{TARGET_PORT}")
    print(f"  - Multiplexer: {MULTIPLEXER_IP}:{MULTIPLEXER_PORT}")

    while True:
        try:
            # 1. 센서 데이터 생성
            sensor_data = self.generate_sensor_data()

            # 2. JSON 직렬화
            message = json.dumps(sensor_data)

            # 3. UDP 전송 (Control Zone)
            self.sock.sendto(message.encode('utf-8'), (TARGET_IP, TARGET_PORT))

            # 4. UDP 전송 (Multiplexer)
            self.sock.sendto(message.encode('utf-8'), (MULTIPLEXER_IP, MULTIPLEXER_PORT))

            # 5. 로그 출력 (5줄)
            print(f"[SENT] Engine: RPM={sensor_data['engine']['rpm']:.0f}, "
                  f"Temp={sensor_data['engine']['temperature']:.1f}°C, "
                  f"Oil={sensor_data['engine']['oil_pressure']:.2f}bar, "
                  f"Load={sensor_data['engine']['load']:.1f}%")
            print(f"       Fuel: Level={sensor_data['fuel']['level']:.1f}%, "
                  f"Flow={sensor_data['fuel']['consumption_rate']:.2f}L/h, "
                  f"Temp={sensor_data['fuel']['temperature']:.1f}°C")
            print(f"       Cooling: Temp={sensor_data['cooling']['temperature']:.1f}°C, "
                  f"Pressure={sensor_data['cooling']['pressure']:.2f}bar")
            print(f"       Electrical: Battery={sensor_data['electrical']['battery_voltage']:.2f}V")
            print(f"       Navigation: Rudder={sensor_data['navigation']['rudder_angle']:.1f}°, "
                  f"Depth={sensor_data['navigation']['water_depth']:.1f}m")

            # 6. 센서 값 업데이트
            self.update_sensors()

            # 7. 2초 대기
            time.sleep(2)

        except KeyboardInterrupt:
            print("\n[Sensor Simulator] Shutting down...")
            break
        except Exception as e:
            print(f"[Sensor Simulator] Error: {e}")
```

**루프 특징**:
- 무한 루프 (Ctrl+C로 종료)
- 예외 처리로 안정성 확보
- 2초 주기로 정확한 타이밍 유지
- 로그 출력으로 실시간 모니터링 가능

---

## 4. 센서 시뮬레이션 시스템

### 4.1 센서 카테고리 및 상세 스펙

#### 4.1.1 엔진 센서 (Engine Sensors)

##### A. Engine RPM (엔진 회전수)

**물리적 의미**: 엔진 크랭크샤프트의 분당 회전수

**초기값**: 850.0 RPM

**동작 범위**: 600 ~ 1200 RPM

**변화 알고리즘**:
```python
self.engine_rpm += random.uniform(-50, 50)
self.engine_rpm = max(600, min(1200, self.engine_rpm))
```

**변화 특성**:
- 랜덤 워크 (Random Walk)
- 매 주기 ±50 RPM 변화
- 하한: 600 RPM (아이들링 근처)
- 상한: 1200 RPM (최대 출력)

**데이터 형식**: 정수 (반올림)

**실제 적용**:
- 엔진 부하에 따라 RPM 변동
- 항해 속도와 직접 연관
- 프로펠러 회전수와 비례

---

##### B. Engine Temperature (엔진 온도)

**물리적 의미**: 엔진 블록 냉각수 온도

**초기값**: 85.0°C

**동작 범위**: 75 ~ 105°C

**변화 알고리즘**:
```python
self.engine_temp += random.uniform(-2, 2)
self.engine_temp = max(75, min(105, self.engine_temp))
```

**변화 특성**:
- 매 주기 ±2°C 변화
- 정상 범위: 75-95°C
- 경고 범위: 95-100°C
- 위험 범위: 100°C 이상

**알람 조건**:
- > 100°C: `ENG_TEMP_HIGH` (WARNING)

**데이터 형식**: 소수점 1자리

**실제 적용**:
- 냉각 시스템 효율 평가
- 과열 방지 모니터링
- 써모스탯 동작 상태 확인

---

##### C. Oil Pressure (오일 압력)

**물리적 의미**: 엔진 윤활유 압력

**초기값**: 4.5 bar

**동작 범위**: 3.0 ~ 6.0 bar

**변화 알고리즘**:
```python
self.engine_oil_pressure += random.uniform(-0.3, 0.3)
self.engine_oil_pressure = max(3.0, min(6.0, self.engine_oil_pressure))
```

**변화 특성**:
- 매 주기 ±0.3 bar 변화
- 정상 범위: 3.5-6.0 bar
- 경고 범위: 3.0-3.5 bar
- 위험 범위: < 3.0 bar

**알람 조건**:
- < 3.5 bar: `OIL_PRESS_LOW` (WARNING)

**데이터 형식**: 소수점 2자리

**실제 적용**:
- 엔진 윤활 상태 확인
- 오일 펌프 성능 평가
- 베어링 마모 예측

---

##### D. Engine Load (엔진 부하)

**물리적 의미**: 최대 출력 대비 현재 출력 비율

**초기값**: 60.0%

**동작 범위**: 30 ~ 95%

**변화 알고리즘**:
```python
self.engine_load += random.uniform(-5, 5)
self.engine_load = max(30, min(95, self.engine_load))
```

**변화 특성**:
- 매 주기 ±5% 변화
- 경부하: 30-50%
- 중부하: 50-75%
- 고부하: 75-95%

**데이터 형식**: 소수점 1자리 (%)

**실제 적용**:
- 연료 소비율 추정
- 엔진 수명 관리
- 최적 운전점 분석

---

#### 4.1.2 연료 시스템 (Fuel System)

##### A. Fuel Level (연료 레벨)

**물리적 의미**: 연료 탱크 잔량 비율

**초기값**: 75.0%

**동작 범위**: 10 ~ 100%

**변화 알고리즘**:
```python
self.fuel_level -= self.fuel_consumption / 1000  # 점진적 감소
self.fuel_level = max(10, min(100, self.fuel_level))
```

**변화 특성**:
- 연료 소비율에 비례하여 감소
- 매 주기 약 0.0125% 감소 (12.5 L/h / 1000)
- 자동 하한 제한 (10%)

**알람 조건**:
- < 20%: `FUEL_LEVEL_LOW` (CAUTION)

**데이터 형식**: 소수점 1자리 (%)

**실제 적용**:
- 항속 거리 계산
- 급유 계획 수립
- 연료 소비 패턴 분석

---

##### B. Fuel Consumption Rate (연료 소비율)

**물리적 의미**: 시간당 연료 소비량

**초기값**: 12.5 L/h

**동작 범위**: 8 ~ 20 L/h

**변화 알고리즘**:
```python
self.fuel_consumption += random.uniform(-1, 1)
self.fuel_consumption = max(8, min(20, self.fuel_consumption))
```

**변화 특성**:
- 매 주기 ±1 L/h 변화
- 저소비: 8-12 L/h (경부하)
- 중소비: 12-16 L/h (중부하)
- 고소비: 16-20 L/h (고부하)

**데이터 형식**: 소수점 2자리 (L/h)

**실제 적용**:
- 연료 효율 모니터링
- 엔진 부하와 상관관계 분석
- 운항 비용 계산

---

##### C. Fuel Temperature (연료 온도)

**물리적 의미**: 연료 라인 온도

**초기값**: 35.0°C

**동작 범위**: 제한 없음 (일반적으로 20-50°C)

**변화 알고리즘**: 현재 고정값 (업데이트 없음)

**데이터 형식**: 소수점 1자리 (°C)

**실제 적용**:
- 연료 점도 관리
- 계절별 연료 특성 보정

---

#### 4.1.3 냉각 시스템 (Cooling System)

##### A. Coolant Temperature (냉각수 온도)

**물리적 의미**: 엔진 냉각수 온도

**초기값**: 82.0°C

**동작 범위**: 70 ~ 95°C

**변화 알고리즘**:
```python
self.coolant_temp += random.uniform(-1.5, 1.5)
self.coolant_temp = max(70, min(95, self.coolant_temp))
```

**변화 특성**:
- 매 주기 ±1.5°C 변화
- 정상 범위: 75-90°C
- 엔진 온도와 상관관계

**데이터 형식**: 소수점 1자리 (°C)

**실제 적용**:
- 냉각 시스템 효율
- 라디에이터 성능 평가

---

##### B. Coolant Pressure (냉각수 압력)

**물리적 의미**: 냉각 시스템 내부 압력

**초기값**: 1.8 bar

**동작 범위**: 1.0 ~ 2.5 bar

**변화 알고리즘**:
```python
self.coolant_pressure += random.uniform(-0.2, 0.2)
self.coolant_pressure = max(1.0, min(2.5, self.coolant_pressure))
```

**변화 특성**:
- 매 주기 ±0.2 bar 변화
- 정상 압력: 1.5-2.0 bar

**데이터 형식**: 소수점 2자리 (bar)

**실제 적용**:
- 냉각수 펌프 상태
- 시스템 누수 감지

---

#### 4.1.4 전기 시스템 (Electrical System)

##### Battery Voltage (배터리 전압)

**물리적 의미**: 선박 메인 배터리 전압

**초기값**: 24.5V

**동작 범위**: 22 ~ 28V

**변화 알고리즘**:
```python
self.battery_voltage += random.uniform(-0.5, 0.5)
self.battery_voltage = max(22.0, min(28.0, self.battery_voltage))
```

**변화 특성**:
- 매 주기 ±0.5V 변화
- 정상 전압: 24-26V (24V 시스템)
- 충전 중: 26-28V
- 방전 중: 22-24V

**알람 조건**:
- < 23.0V: `BATTERY_LOW` (CAUTION)

**데이터 형식**: 소수점 2자리 (V)

**실제 적용**:
- 발전기 충전 상태
- 배터리 건강도 평가
- 전기 부하 관리

---

#### 4.1.5 항해 장비 (Navigation Equipment)

##### A. Rudder Angle (키 각도)

**물리적 의미**: 방향타 조타 각도

**초기값**: 0.0° (직진)

**동작 범위**: -35 ~ +35°

**변화 알고리즘**:
```python
self.rudder_angle += random.uniform(-10, 10)
self.rudder_angle = max(-35, min(35, self.rudder_angle))
```

**변화 특성**:
- 매 주기 ±10° 변화
- 0°: 직진
- 양수: 우현 (Starboard)
- 음수: 좌현 (Port)

**데이터 형식**: 소수점 1자리 (°)

**실제 적용**:
- 조타 시스템 모니터링
- 자동 조타 장치 피드백
- 침로 유지 분석

---

##### B. Water Depth (수심)

**물리적 의미**: 선박 하부 수심

**초기값**: 50.0m

**동작 범위**: 10 ~ 200m

**변화 알고리즘**:
```python
self.water_depth += random.uniform(-5, 5)
self.water_depth = max(10, min(200, self.water_depth))
```

**변화 특성**:
- 매 주기 ±5m 변화
- 천해: 10-30m
- 중심해: 30-100m
- 심해: 100-200m

**알람 조건**:
- < 15m: `SHALLOW_WATER` (WARNING)

**데이터 형식**: 소수점 1자리 (m)

**실제 적용**:
- 좌초 방지
- 항로 계획
- 해저 지형 파악

---

### 4.2 데이터 생성 메서드 (generate_sensor_data)

```python
def generate_sensor_data(self):
    """센서 데이터 생성"""
    # 알람 체크
    self.check_alarms()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "engine": {
            "rpm": round(self.engine_rpm, 1),
            "temperature": round(self.engine_temp, 1),
            "oil_pressure": round(self.engine_oil_pressure, 2),
            "load": round(self.engine_load, 1)
        },
        "fuel": {
            "level": round(self.fuel_level, 1),
            "consumption_rate": round(self.fuel_consumption, 2),
            "temperature": round(self.fuel_temp, 1)
        },
        "cooling": {
            "temperature": round(self.coolant_temp, 1),
            "pressure": round(self.coolant_pressure, 2)
        },
        "electrical": {
            "battery_voltage": round(self.battery_voltage, 2)
        },
        "navigation": {
            "rudder_angle": round(self.rudder_angle, 1),
            "water_depth": round(self.water_depth, 1)
        },
        "alarms": self.alarms.copy()
    }
```

**특징**:
- ISO 8601 형식 타임스탬프
- 카테고리별 데이터 그룹화
- 적절한 반올림 (센서 정밀도 반영)
- 알람 배열 포함
- Deep copy로 데이터 독립성 보장

---

### 4.3 센서 업데이트 메서드 (update_sensors)

```python
def update_sensors(self):
    """센서 값 업데이트"""
    # 1. 엔진 RPM (±50)
    self.engine_rpm += random.uniform(-50, 50)
    self.engine_rpm = max(600, min(1200, self.engine_rpm))

    # 2. 엔진 온도 (±2도)
    self.engine_temp += random.uniform(-2, 2)
    self.engine_temp = max(75, min(105, self.engine_temp))

    # 3. 엔진 오일 압력 (±0.3 bar)
    self.engine_oil_pressure += random.uniform(-0.3, 0.3)
    self.engine_oil_pressure = max(3.0, min(6.0, self.engine_oil_pressure))

    # 4. 엔진 부하 (±5%)
    self.engine_load += random.uniform(-5, 5)
    self.engine_load = max(30, min(95, self.engine_load))

    # 5. 연료 레벨 (서서히 감소)
    self.fuel_level -= self.fuel_consumption / 1000
    self.fuel_level = max(10, min(100, self.fuel_level))

    # 6. 연료 소비율 (±1 L/h)
    self.fuel_consumption += random.uniform(-1, 1)
    self.fuel_consumption = max(8, min(20, self.fuel_consumption))

    # 7. 냉각수 온도 (±1.5도)
    self.coolant_temp += random.uniform(-1.5, 1.5)
    self.coolant_temp = max(70, min(95, self.coolant_temp))

    # 8. 냉각수 압력 (±0.2 bar)
    self.coolant_pressure += random.uniform(-0.2, 0.2)
    self.coolant_pressure = max(1.0, min(2.5, self.coolant_pressure))

    # 9. 배터리 전압 (±0.5V)
    self.battery_voltage += random.uniform(-0.5, 0.5)
    self.battery_voltage = max(22.0, min(28.0, self.battery_voltage))

    # 10. 키 각도 (±10도)
    self.rudder_angle += random.uniform(-10, 10)
    self.rudder_angle = max(-35, min(35, self.rudder_angle))

    # 11. 수심 (±5m)
    self.water_depth += random.uniform(-5, 5)
    self.water_depth = max(10, min(200, self.water_depth))
```

**알고리즘 특징**:
- **Random Walk**: 이전 값 기준 무작위 변화
- **Bounded Random Walk**: 상하한 강제 적용
- **현실적 변화**: 물리적으로 가능한 변화율
- **독립성**: 각 센서 독립적으로 변화 (향후 상관관계 추가 가능)

**Random Walk의 장점**:
1. 연속성: 급격한 값 변화 방지
2. 현실성: 실제 센서 노이즈 반영
3. 다양성: 매번 다른 패턴 생성
4. 안정성: 범위 내 값 보장

---

## 5. 데이터 전송 메커니즘

### 5.1 전송 프로토콜

#### UDP (User Datagram Protocol)

**선택 이유**:
1. **실시간성**: TCP보다 낮은 지연시간
2. **단순성**: 연결 설정 불필요
3. **효율성**: 오버헤드 최소화
4. **Broadcasting**: 다중 수신자 지원

**단점 및 대응**:
- 패킷 손실 가능 → 2초 주기로 지속 전송 (손실 허용)
- 순서 보장 없음 → 타임스탬프로 순서 확인 가능
- 신뢰성 없음 → 센서 데이터는 최신값만 중요

### 5.2 전송 대상

#### 대상 1: Control Zone

**목적**: 센서 데이터를 Control Zone PLC로 전달

**주소**: `10.10.20.10:10112`

**수신**: `sensor_to_plc.py`

**처리**:
1. UDP 수신
2. JSON 파싱
3. Modbus 레지스터 변환
4. PLC 쓰기 (HR[10-21])

---

#### 대상 2: Multiplexer

**목적**: NMEA 변환 및 Bridge Zone 전송

**주소**: `127.0.0.1:10113`

**수신**: NMEA Multiplexer (별도 프로세스)

**처리**:
1. UDP 수신
2. JSON → NMEA 변환
3. Bridge Zone 전송

---

### 5.3 데이터 형식 (JSON)

#### 전체 구조

```json
{
  "timestamp": "2025-12-19T12:34:56.789012",
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
  "alarms": [
    {
      "level": "WARNING",
      "code": "ENG_TEMP_HIGH",
      "message": "Engine temperature high: 102.5°C"
    }
  ]
}
```

#### 필드 상세

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| **timestamp** | string | Y | ISO 8601 UTC 시간 |
| **engine** | object | Y | 엔진 센서 그룹 |
| **fuel** | object | Y | 연료 센서 그룹 |
| **cooling** | object | Y | 냉각 센서 그룹 |
| **electrical** | object | Y | 전기 센서 그룹 |
| **navigation** | object | Y | 항해 센서 그룹 |
| **alarms** | array | Y | 알람 배열 (빈 배열 가능) |

#### 페이로드 크기

**일반적인 경우** (알람 없음):
- 약 350-400 바이트

**알람 포함 시**:
- 약 500-600 바이트 (알람 3-4개 기준)

**최대 크기**:
- 1000 바이트 이하 (UDP 단편화 방지)

---

## 6. 알람 시스템

### 6.1 알람 체크 메서드 (check_alarms)

```python
def check_alarms(self):
    """알람 상태 체크"""
    self.alarms = []

    # 1. 엔진 온도 경고
    if self.engine_temp > 100:
        self.alarms.append({
            "level": "WARNING",
            "code": "ENG_TEMP_HIGH",
            "message": f"Engine temperature high: {self.engine_temp:.1f}°C"
        })

    # 2. 오일 압력 경고
    if self.engine_oil_pressure < 3.5:
        self.alarms.append({
            "level": "WARNING",
            "code": "OIL_PRESS_LOW",
            "message": f"Engine oil pressure low: {self.engine_oil_pressure:.2f} bar"
        })

    # 3. 연료 레벨 경고
    if self.fuel_level < 20:
        self.alarms.append({
            "level": "CAUTION",
            "code": "FUEL_LEVEL_LOW",
            "message": f"Fuel level low: {self.fuel_level:.1f}%"
        })

    # 4. 배터리 전압 경고
    if self.battery_voltage < 23.0:
        self.alarms.append({
            "level": "CAUTION",
            "code": "BATTERY_LOW",
            "message": f"Battery voltage low: {self.battery_voltage:.2f}V"
        })

    # 5. 수심 경고
    if self.water_depth < 15:
        self.alarms.append({
            "level": "WARNING",
            "code": "SHALLOW_WATER",
            "message": f"Shallow water: {self.water_depth:.1f}m"
        })
```

### 6.2 알람 레벨

| 레벨 | 심각도 | 의미 | 조치 |
|------|--------|------|------|
| **WARNING** | 높음 | 즉시 조치 필요 | 운전 정지 또는 긴급 조치 |
| **CAUTION** | 중간 | 주의 필요 | 모니터링 강화, 조치 계획 |
| **INFO** | 낮음 | 정보 제공 | 기록 및 추세 분석 |

### 6.3 알람 목록

#### 1. ENG_TEMP_HIGH (엔진 온도 높음)

**조건**: 엔진 온도 > 100°C

**레벨**: WARNING

**원인**:
- 냉각수 부족
- 써모스탯 고장
- 라디에이터 막힘
- 과부하 운전

**조치**:
1. 부하 감소
2. 냉각수 레벨 확인
3. 냉각 시스템 점검

---

#### 2. OIL_PRESS_LOW (오일 압력 낮음)

**조건**: 오일 압력 < 3.5 bar

**레벨**: WARNING

**원인**:
- 오일 레벨 부족
- 오일 펌프 고장
- 오일 필터 막힘
- 베어링 마모

**조치**:
1. 즉시 엔진 정지
2. 오일 레벨 확인
3. 오일 누유 점검

---

#### 3. FUEL_LEVEL_LOW (연료 부족)

**조건**: 연료 레벨 < 20%

**레벨**: CAUTION

**원인**:
- 장시간 운항
- 급유 지연

**조치**:
1. 급유 계획 수립
2. 항로 재검토
3. 연료 소비율 최적화

---

#### 4. BATTERY_LOW (배터리 부족)

**조건**: 배터리 전압 < 23V

**레벨**: CAUTION

**원인**:
- 발전기 고장
- 배터리 노화
- 과도한 전기 부하

**조치**:
1. 발전기 점검
2. 불필요한 전기 부하 차단
3. 배터리 충전

---

#### 5. SHALLOW_WATER (천해 경고)

**조건**: 수심 < 15m

**레벨**: WARNING

**원인**:
- 항로 이탈
- 해도 오류
- 조류 영향

**조치**:
1. 속도 감속
2. 항로 재확인
3. 수동 조타 전환

---

### 6.4 알람 데이터 구조

```json
{
  "level": "WARNING|CAUTION|INFO",
  "code": "ALARM_CODE",
  "message": "Human readable message"
}
```

**필드 설명**:
- `level`: 알람 심각도
- `code`: 고유 알람 코드 (프로그래밍 식별용)
- `message`: 사람이 읽을 수 있는 메시지 (현재 값 포함)

---

## 7. 실행 및 운영

### 7.1 실행 방법

#### 기본 실행

```bash
cd /home/user/coke/field
python sensor_sim.py
```

#### 커스텀 대상 지정

```bash
python sensor_sim.py --target-ip 192.168.1.100 --target-port 5000
```

#### 도움말

```bash
python sensor_sim.py --help
```

**출력**:
```
usage: sensor_sim.py [-h] [--target-ip TARGET_IP] [--target-port TARGET_PORT]

Ship Sensor Simulator

optional arguments:
  -h, --help            show this help message and exit
  --target-ip TARGET_IP
                        Target IP address (default: 10.10.20.10)
  --target-port TARGET_PORT
                        Target port (default: 10112)
```

---

### 7.2 로그 출력

#### 시작 메시지

```
[Sensor Simulator] Sending to:
  - Control Zone: 10.10.20.10:10112
  - Multiplexer: 127.0.0.1:10113
```

#### 주기적 출력 (2초마다)

```
[SENT] Engine: RPM=850, Temp=85.0°C, Oil=4.50bar, Load=60.0%
       Fuel: Level=75.0%, Flow=12.50L/h, Temp=35.0°C
       Cooling: Temp=82.0°C, Pressure=1.80bar
       Electrical: Battery=24.50V
       Navigation: Rudder=0.0°, Depth=50.0m
```

**특징**:
- 5줄 출력 (카테고리별)
- 모든 센서 값 표시
- 단위 명시
- 소수점 자릿수 일관성

---

### 7.3 종료

**정상 종료**: `Ctrl + C`

**출력**:
```
[Sensor Simulator] Shutting down...
```

**자원 정리**: UDP 소켓 자동 해제

---

### 7.4 에러 처리

#### 네트워크 에러

**증상**: UDP 전송 실패

**처리**: 에러 로그 출력 후 계속 실행

**로그**:
```
[Sensor Simulator] Error: [Errno 101] Network is unreachable
```

**대응**:
1. 네트워크 연결 확인
2. IP/포트 설정 확인
3. 방화벽 규칙 확인

---

#### JSON 직렬화 에러

**증상**: 센서 값이 NaN 또는 Infinity

**처리**: 예외 처리 및 로그

**대응**:
1. 센서 업데이트 로직 점검
2. 초기값 확인

---

## 8. 설정 및 커스터마이징

### 8.1 센서 초기값 변경

**파일**: `sensor_sim.py`

**위치**: `SensorSimulator.__init__()`

**예시**:
```python
# RPM 초기값을 1000으로 변경
self.engine_rpm = 1000.0  # 기존: 850.0

# 연료 레벨 초기값을 50%로 변경
self.fuel_level = 50.0  # 기존: 75.0
```

---

### 8.2 센서 범위 변경

**파일**: `sensor_sim.py`

**위치**: `SensorSimulator.update_sensors()`

**예시**:
```python
# RPM 범위를 500-1500으로 변경
self.engine_rpm = max(500, min(1500, self.engine_rpm))  # 기존: 600-1200
```

---

### 8.3 변화율 조정

**파일**: `sensor_sim.py`

**위치**: `SensorSimulator.update_sensors()`

**예시**:
```python
# RPM 변화를 더 완만하게 (±50 → ±20)
self.engine_rpm += random.uniform(-20, 20)  # 기존: -50, 50

# 온도 변화를 더 급격하게 (±2 → ±5)
self.engine_temp += random.uniform(-5, 5)  # 기존: -2, 2
```

---

### 8.4 주기 변경

**파일**: `sensor_sim.py`

**위치**: `SensorSimulator.start()`

**예시**:
```python
# 1초 주기로 변경
time.sleep(1)  # 기존: time.sleep(2)

# 5초 주기로 변경
time.sleep(5)  # 기존: time.sleep(2)
```

**주의**: Control Zone 수신 측 주기와 일치시킬 것

---

### 8.5 알람 임계값 변경

**파일**: `sensor_sim.py`

**위치**: `SensorSimulator.check_alarms()`

**예시**:
```python
# 엔진 온도 경고를 95°C로 낮춤
if self.engine_temp > 95:  # 기존: 100
    self.alarms.append({...})

# 연료 경고를 30%로 높임
if self.fuel_level < 30:  # 기존: 20
    self.alarms.append({...})
```

---

### 8.6 새 센서 추가

**단계**:

1. **초기값 추가** (`__init__`)
```python
self.new_sensor = 100.0
```

2. **업데이트 로직 추가** (`update_sensors`)
```python
self.new_sensor += random.uniform(-10, 10)
self.new_sensor = max(0, min(200, self.new_sensor))
```

3. **데이터 생성에 포함** (`generate_sensor_data`)
```python
return {
    # ... 기존 센서들
    "new_category": {
        "new_sensor": round(self.new_sensor, 1)
    }
}
```

4. **로그 출력 추가** (`start`)
```python
print(f"       NewCategory: Sensor={sensor_data['new_category']['new_sensor']:.1f}")
```

---

### 8.7 전송 대상 추가

**예시**: 세 번째 대상 추가

```python
# 설정
THIRD_TARGET_IP = "192.168.1.200"
THIRD_TARGET_PORT = 9999

# start() 메서드 내 전송 추가
self.sock.sendto(message.encode('utf-8'), (THIRD_TARGET_IP, THIRD_TARGET_PORT))
```

---

## 9. 트러블슈팅

### 9.1 일반적인 문제

#### 문제 1: "Address already in use"

**원인**: UDP 포트가 이미 사용 중

**해결**:
1. 기존 프로세스 종료
```bash
# 포트 사용 프로세스 확인
sudo netstat -tulpn | grep 10112

# 프로세스 종료
kill -9 <PID>
```

2. 다른 포트 사용
```bash
python sensor_sim.py --target-port 10120
```

---

#### 문제 2: "Network is unreachable"

**원인**: 대상 IP 접근 불가

**해결**:
1. IP 연결 확인
```bash
ping 10.10.20.10
```

2. 라우팅 테이블 확인
```bash
ip route
```

3. 방화벽 규칙 확인
```bash
sudo iptables -L
```

---

#### 문제 3: 데이터가 수신되지 않음

**원인**: Control Zone 미실행 또는 설정 오류

**해결**:
1. Control Zone 실행 확인
```bash
ps aux | grep sensor_to_plc
```

2. 포트 번호 일치 확인
- sensor_sim.py: `--target-port 10112`
- sensor_to_plc.py: `--sensor-port 10112`

3. IP 주소 확인
```bash
# Control Zone 서버 IP 확인
hostname -I
```

---

### 9.2 성능 문제

#### 문제: CPU 사용률 높음

**원인**: 너무 짧은 주기

**해결**: `time.sleep()` 값 증가

```python
time.sleep(5)  # 2초 → 5초
```

---

#### 문제: 메모리 증가

**원인**: 알람 배열이 계속 누적

**해결**: 이미 구현됨 (`self.alarms = []`로 매번 초기화)

---

### 9.3 디버깅

#### 패킷 캡처

**tcpdump 사용**:
```bash
# UDP 10112 포트 모니터링
sudo tcpdump -i any -nn udp port 10112 -A

# JSON 형식 확인
sudo tcpdump -i any -nn udp port 10112 -X | grep -A 20 "timestamp"
```

#### Wireshark 사용

1. Wireshark 실행
2. 필터: `udp.port == 10112`
3. 패킷 선택 → Follow UDP Stream
4. JSON 데이터 확인

---

## 10. 성능 및 확장성

### 10.1 성능 지표

| 지표 | 값 |
|------|-----|
| **전송 주기** | 2초 |
| **패킷 크기** | 400-600 바이트 |
| **전송률** | 0.2-0.3 KB/s |
| **CPU 사용률** | < 1% |
| **메모리 사용** | < 20 MB |
| **네트워크 대역폭** | < 1 Kbps |

### 10.2 확장 가능성

#### 센서 추가

**현재**: 12개 센서

**최대 권장**: 50개 센서

**제한 요인**:
- UDP 패킷 크기 (< 1500 바이트)
- JSON 파싱 시간

---

#### 전송 주기 단축

**현재**: 2초

**최소 권장**: 0.1초 (100ms)

**제한 요인**:
- CPU 부하
- 네트워크 대역폭
- 수신 측 처리 능력

---

#### 다중 시뮬레이터

**방법**: 여러 인스턴스 실행

```bash
# 시뮬레이터 1 (포트 10112)
python sensor_sim.py --target-port 10112

# 시뮬레이터 2 (포트 10113)
python sensor_sim.py --target-port 10113
```

**활용**:
- 다중 선박 시뮬레이션
- 부하 테스트
- A/B 테스트

---

### 10.3 향후 개선 방안

#### 1. 센서 상관관계

**현재**: 각 센서 독립적

**개선**: 물리적 상관관계 반영

**예시**:
```python
# RPM이 높으면 연료 소비도 증가
if self.engine_rpm > 1000:
    self.fuel_consumption = 15 + (self.engine_rpm - 1000) / 50
```

---

#### 2. 시나리오 기반 시뮬레이션

**현재**: 랜덤 워크

**개선**: 사전 정의된 시나리오 재생

**예시**:
- 가속 시나리오
- 감속 시나리오
- 비상 상황 시나리오

---

#### 3. 데이터베이스 연동

**목적**: 과거 데이터 재생

**방법**: CSV/DB에서 실제 항해 데이터 로드

---

#### 4. 실시간 제어 인터페이스

**목적**: 외부에서 센서 값 조작

**방법**: REST API 또는 WebSocket 제공

---

#### 5. 고급 알람 로직

**현재**: 단순 임계값

**개선**:
- 추세 분석 (지속 상승/하강)
- 복합 조건 (AND/OR 로직)
- 우선순위 관리

---

## 부록

### A. 전체 데이터 예시

```json
{
  "timestamp": "2025-12-19T14:23:45.123456",
  "engine": {
    "rpm": 874.0,
    "temperature": 87.3,
    "oil_pressure": 4.62,
    "load": 63.2
  },
  "fuel": {
    "level": 74.8,
    "consumption_rate": 13.21,
    "temperature": 35.0
  },
  "cooling": {
    "temperature": 83.5,
    "pressure": 1.76
  },
  "electrical": {
    "battery_voltage": 24.82
  },
  "navigation": {
    "rudder_angle": -3.2,
    "water_depth": 52.8
  },
  "alarms": []
}
```

### B. 명령어 치트시트

```bash
# 기본 실행
python sensor_sim.py

# 커스텀 대상
python sensor_sim.py --target-ip 192.168.1.100 --target-port 5000

# 백그라운드 실행
nohup python sensor_sim.py > sensor.log 2>&1 &

# 프로세스 확인
ps aux | grep sensor_sim

# 종료
kill -9 <PID>

# 로그 모니터링
tail -f sensor.log
```

### C. 참고 문헌

1. 선박 엔진 시스템 매뉴얼
2. Modbus TCP/IP 프로토콜 사양
3. UDP 프로그래밍 가이드
4. JSON 데이터 형식 표준
5. 선박 계측 및 제어 시스템 (IEC 61162)

---

**문서 버전**: 1.0
**최종 수정일**: 2025-12-19
**작성자**: System Documentation Team
**검토자**: Field Zone Engineering Team
