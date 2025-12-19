# Field Zone - Python 코드 상세 분석 보고서

## 목차
1. [개요](#1-개요)
2. [파일 구조](#2-파일-구조)
3. [sensor_sim.py 전체 코드 분석](#3-sensor_simpy-전체-코드-분석)
4. [Import 문 분석](#4-import-문-분석)
5. [전역 변수 분석](#5-전역-변수-분석)
6. [SensorSimulator 클래스 분석](#6-sensorsimulator-클래스-분석)
7. [메서드별 상세 분석](#7-메서드별-상세-분석)
8. [메인 실행 부분 분석](#8-메인-실행-부분-분석)
9. [코드 실행 흐름](#9-코드-실행-흐름)
10. [코드 품질 및 개선점](#10-코드-품질-및-개선점)

---

## 1. 개요

### 1.1 파일 정보

- **파일명**: `sensor_sim.py`
- **경로**: `/home/user/coke/field/sensor_sim.py`
- **역할**: Field Zone 센서 시뮬레이터
- **언어**: Python 3.x
- **총 라인 수**: 약 220줄
- **주요 기능**: 12개 센서 데이터 생성 및 UDP 전송

### 1.2 코드 개요

이 파일은 선박 엔진 모니터링 시스템의 Field Zone을 구현합니다. 실제 하드웨어 센서를 시뮬레이션하여 엔진, 연료, 냉각, 전기, 항해 관련 데이터를 생성하고 Control Zone으로 전송합니다.

---

## 2. 파일 구조

```
sensor_sim.py
├── 1. 파일 독스트링 (라인 1-4)
├── 2. Import 문 (라인 5-10)
├── 3. 전역 설정 변수 (라인 12-17)
├── 4. SensorSimulator 클래스 (라인 19-200)
│   ├── __init__ 메서드 (라인 20-45)
│   ├── start 메서드 (라인 47-78)
│   ├── generate_sensor_data 메서드 (라인 80-109)
│   ├── update_sensors 메서드 (라인 111-156)
│   └── check_alarms 메서드 (라인 158-200)
└── 5. 메인 실행 블록 (라인 202-218)
```

---

## 3. sensor_sim.py 전체 코드 분석

### 3.1 파일 독스트링 (라인 1-4)

```python
"""
Ship Sensor Simulator
선박 센서 시뮬레이터 (엔진, 연료, 온도 등)
"""
```

**설명**:
- Python 파일의 목적을 설명하는 독스트링
- 한글과 영어로 이중 표기
- 주요 기능을 간단히 명시

**목적**:
- 코드 문서화
- IDE에서 파일 정보 표시
- `help(sensor_sim)` 명령 시 출력

---

## 4. Import 문 분석

### 4.1 표준 라이브러리 Import (라인 6-10)

```python
import time
import random
import socket
import json
from datetime import datetime
```

#### 4.1.1 time 모듈

**용도**: 시간 지연 및 타이밍 제어

**사용 위치**:
- `time.sleep(2)`: 2초 대기 (라인 75)

**이유**:
- 센서 데이터를 2초 주기로 전송하기 위함
- CPU 사용률 절감

---

#### 4.1.2 random 모듈

**용도**: 난수 생성

**사용 위치**:
- `random.uniform(min, max)`: 균등 분포 실수 난수 생성
- 센서 값 업데이트에 사용 (라인 114-155)

**예시**:
```python
self.engine_rpm += random.uniform(-50, 50)
```

**이유**:
- Random Walk 알고리즘 구현
- 현실적인 센서 노이즈 시뮬레이션

---

#### 4.1.3 socket 모듈

**용도**: 네트워크 통신 (UDP)

**사용 위치**:
- UDP 소켓 생성 (라인 21)
- 데이터 전송 (라인 61, 64)

**코드**:
```python
self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
```

**파라미터 설명**:
- `socket.AF_INET`: IPv4 주소 체계
- `socket.SOCK_DGRAM`: UDP 프로토콜

---

#### 4.1.4 json 모듈

**용도**: JSON 직렬화/역직렬화

**사용 위치**:
- `json.dumps(sensor_data)`: Python dict → JSON 문자열 (라인 58)

**예시**:
```python
message = json.dumps(sensor_data)
```

**이유**:
- 구조화된 데이터 전송
- 플랫폼 독립적 데이터 형식
- 사람이 읽기 쉬운 형식

---

#### 4.1.5 datetime 모듈

**용도**: 타임스탬프 생성

**사용 위치**:
- `datetime.utcnow().isoformat()`: UTC 시간을 ISO 8601 형식으로 변환 (라인 85)

**출력 예시**:
```
"2025-12-19T14:23:45.123456"
```

**이유**:
- 데이터 수신 시간 기록
- 시계열 데이터 분석
- 국제 표준 시간 형식

---

## 5. 전역 변수 분석

### 5.1 네트워크 설정 변수 (라인 12-17)

```python
TARGET_IP = "10.10.20.10"
TARGET_PORT = 10112

# Multiplexer 설정 (Bridge Zone용 NMEA 변환)
MULTIPLEXER_IP = "127.0.0.1"
MULTIPLEXER_PORT = 10113
```

#### 5.1.1 TARGET_IP

**값**: `"10.10.20.10"`

**의미**: Control Zone의 IP 주소

**용도**: 센서 데이터를 전송할 대상 주소

**네트워크 구조**:
```
Field Zone (sensor_sim.py)
    ↓ UDP
10.10.20.10:10112 (Control Zone - sensor_to_plc.py)
```

**변경 방법**:
- 명령줄 인자: `--target-ip 192.168.1.100`
- 코드 수정: `TARGET_IP = "새주소"`

---

#### 5.1.2 TARGET_PORT

**값**: `10112`

**의미**: Control Zone의 UDP 수신 포트

**포트 선택 이유**:
- 1024 이상의 비특권 포트
- Well-known 포트와 충돌 방지
- 프로젝트 고유 번호

---

#### 5.1.3 MULTIPLEXER_IP

**값**: `"127.0.0.1"` (localhost)

**의미**: 로컬 머신에서 실행 중인 Multiplexer

**용도**: NMEA 0183 프로토콜로 변환하여 Bridge Zone 전송

---

#### 5.1.4 MULTIPLEXER_PORT

**값**: `10113`

**의미**: Multiplexer UDP 수신 포트

**참고**: Control Zone과 다른 포트 사용 (10112 vs 10113)

---

## 6. SensorSimulator 클래스 분석

### 6.1 클래스 정의 (라인 19)

```python
class SensorSimulator:
```

**클래스명**: `SensorSimulator`

**명명 규칙**: PascalCase (파이썬 클래스 네이밍 컨벤션)

**역할**: 센서 시뮬레이터의 상태와 동작을 캡슐화

**객체지향 설계**:
- 센서 상태를 인스턴스 변수로 관리
- 센서 동작을 메서드로 구현
- 재사용 가능한 컴포넌트

---

### 6.2 생성자 메서드 (__init__)

#### 6.2.1 메서드 시그니처 (라인 20)

```python
def __init__(self):
```

**파라미터**: 없음 (self만 존재)

**반환값**: 없음 (생성자는 None 반환)

**호출 시점**: `SensorSimulator()` 객체 생성 시

---

#### 6.2.2 UDP 소켓 생성 (라인 21-22)

```python
# UDP 소켓 생성
self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
```

**코드 분석**:
- `socket.socket()`: 새 소켓 객체 생성
- `AF_INET`: IPv4 주소 체계 사용
- `SOCK_DGRAM`: 데이터그램 소켓 (UDP)

**메모리 할당**:
- 운영체제 수준의 소켓 버퍼 할당
- 파일 디스크립터 생성

**주의사항**:
- 프로그램 종료 시 소켓 닫기 필요
- 현재 코드에는 명시적 `close()` 없음 (프로세스 종료 시 자동 해제)

---

#### 6.2.3 엔진 센서 초기화 (라인 24-27)

```python
# 엔진 센서 (메인 엔진)
self.engine_rpm = 850.0
self.engine_temp = 85.0  # Celsius
self.engine_oil_pressure = 4.5  # bar
self.engine_load = 60.0  # percentage
```

##### A. self.engine_rpm = 850.0

**타입**: float

**초기값**: 850.0 RPM

**의미**: 엔진 크랭크샤프트 분당 회전수

**선택 이유**:
- 일반적인 선박 엔진 아이들링 속도
- 정상 운전 범위 중간값
- 상승/하강 여유 확보

**단위**: RPM (Revolutions Per Minute)

---

##### B. self.engine_temp = 85.0

**타입**: float

**초기값**: 85.0°C

**의미**: 엔진 냉각수 온도

**선택 이유**:
- 정상 운전 온도 범위 (75-95°C)
- 써모스탯 개방 온도 근처
- 과열 경고 임계값(100°C)과 충분한 여유

**단위**: °C (Celsius)

---

##### C. self.engine_oil_pressure = 4.5

**타입**: float

**초기값**: 4.5 bar

**의미**: 엔진 윤활유 압력

**선택 이유**:
- 정상 오일 압력 범위 (3.5-6.0 bar)
- 베어링 보호에 충분한 압력
- 경고 임계값(3.5 bar) 이상

**단위**: bar (1 bar = 100 kPa)

---

##### D. self.engine_load = 60.0

**타입**: float

**초기값**: 60.0%

**의미**: 최대 출력 대비 현재 출력 비율

**선택 이유**:
- 중간 부하 상태
- 연료 효율과 출력의 균형
- 가속/감속 여유

**단위**: % (percentage)

---

#### 6.2.4 연료 시스템 초기화 (라인 29-32)

```python
# 연료 시스템
self.fuel_level = 75.0  # percentage
self.fuel_consumption = 12.5  # L/hour
self.fuel_temp = 35.0  # Celsius
```

##### A. self.fuel_level = 75.0

**타입**: float

**초기값**: 75.0%

**의미**: 연료 탱크 잔량 비율

**선택 이유**:
- 충분한 연료 보유
- 급유 경고(20%) 훨씬 상회
- 장시간 시뮬레이션 가능

**변화 특성**: 시간에 따라 감소 (연료 소비)

---

##### B. self.fuel_consumption = 12.5

**타입**: float

**초기값**: 12.5 L/h

**의미**: 시간당 연료 소비량

**선택 이유**:
- 중간 부하 운전의 전형적 소비율
- 연료 레벨 감소 속도 결정

**영향 요인**:
- 엔진 부하
- RPM
- 항해 속도

---

##### C. self.fuel_temp = 35.0

**타입**: float

**초기값**: 35.0°C

**의미**: 연료 라인 온도

**특징**: 현재 업데이트 로직 없음 (고정값)

**실제 영향**: 연료 점도, 분사 특성

---

#### 6.2.5 냉각 시스템 초기화 (라인 34-36)

```python
# 냉각 시스템
self.coolant_temp = 82.0  # Celsius
self.coolant_pressure = 1.8  # bar
```

##### A. self.coolant_temp = 82.0

**타입**: float

**초기값**: 82.0°C

**의미**: 냉각수 온도

**관계**: 엔진 온도와 밀접한 상관관계

**정상 범위**: 75-90°C

---

##### B. self.coolant_pressure = 1.8

**타입**: float

**초기값**: 1.8 bar

**의미**: 냉각 시스템 내부 압력

**목적**: 비등점 상승 (압력↑ → 비등점↑)

**정상 범위**: 1.5-2.0 bar

---

#### 6.2.6 전기 시스템 초기화 (라인 38-39)

```python
# 기타 센서
self.battery_voltage = 24.5  # V
```

**타입**: float

**초기값**: 24.5V

**의미**: 메인 배터리 전압

**시스템 전압**: 24V 시스템

**정상 범위**: 24-26V

**충전 중**: 26-28V

**방전 중**: 22-24V

---

#### 6.2.7 항해 장비 초기화 (라인 40-41)

```python
self.rudder_angle = 0.0  # degrees
self.water_depth = 50.0  # meters
```

##### A. self.rudder_angle = 0.0

**타입**: float

**초기값**: 0.0° (직진)

**의미**: 방향타 조타 각도

**범위**: -35° ~ +35°

**부호 규칙**:
- 양수(+): 우현 (Starboard)
- 음수(-): 좌현 (Port)
- 0: 직진

---

##### B. self.water_depth = 50.0

**타입**: float

**초기값**: 50.0m

**의미**: 선박 하부 수심

**범위**: 10-200m

**용도**: 좌초 방지, 항로 확인

---

#### 6.2.8 알람 리스트 초기화 (라인 43-44)

```python
# 알람 상태
self.alarms = []
```

**타입**: list

**초기값**: 빈 리스트 `[]`

**용도**: 활성 알람 저장

**구조**: 각 알람은 dict 형태
```python
{
    "level": "WARNING",
    "code": "ENG_TEMP_HIGH",
    "message": "Engine temperature high: 102.5°C"
}
```

**업데이트**: `check_alarms()` 메서드에서 매번 재생성

---

## 7. 메서드별 상세 분석

### 7.1 start 메서드 (라인 47-78)

#### 7.1.1 메서드 시그니처

```python
def start(self):
    """센서 시뮬레이터 시작"""
```

**파라미터**: 없음

**반환값**: 없음

**역할**: 메인 실행 루프

---

#### 7.1.2 시작 메시지 출력 (라인 48-50)

```python
print(f"[Sensor Simulator] Sending to:")
print(f"  - Control Zone: {TARGET_IP}:{TARGET_PORT}")
print(f"  - Multiplexer: {MULTIPLEXER_IP}:{MULTIPLEXER_PORT}")
```

**출력 예시**:
```
[Sensor Simulator] Sending to:
  - Control Zone: 10.10.20.10:10112
  - Multiplexer: 127.0.0.1:10113
```

**목적**:
- 사용자에게 전송 대상 확인
- 네트워크 설정 검증 기회
- 디버깅 정보 제공

**f-string 사용**:
- Python 3.6+ 문자열 포맷팅
- 변수 값 직접 삽입
- 가독성 우수

---

#### 7.1.3 무한 루프 시작 (라인 52)

```python
while True:
```

**제어 구조**: 무한 루프

**종료 조건**:
- Ctrl+C (KeyboardInterrupt)
- 프로그램 강제 종료
- 예외 발생

**이유**: 센서는 계속 동작해야 함

---

#### 7.1.4 예외 처리 블록 시작 (라인 53)

```python
try:
```

**목적**:
- 런타임 에러 포착
- 프로그램 안정성 향상
- 에러 로깅

---

#### 7.1.5 센서 데이터 생성 (라인 55)

```python
# 센서 데이터 생성
sensor_data = self.generate_sensor_data()
```

**호출 메서드**: `generate_sensor_data()`

**반환값**: dict (센서 데이터 JSON 구조)

**내부 동작**:
1. `check_alarms()` 호출
2. 현재 센서 값 읽기
3. dict 구조로 구성
4. 타임스탬프 추가

---

#### 7.1.6 JSON 직렬화 (라인 58)

```python
# JSON 형식으로 전송
message = json.dumps(sensor_data)
```

**함수**: `json.dumps()`

**입력**: Python dict

**출력**: JSON 문자열

**예시**:
```python
# 입력
{"engine": {"rpm": 850.0}}

# 출력
'{"engine": {"rpm": 850.0}}'
```

**옵션**: 기본 설정 사용 (들여쓰기 없음, 압축)

---

#### 7.1.7 Control Zone 전송 (라인 61)

```python
# 1) Control Zone으로 전송
self.sock.sendto(message.encode('utf-8'), (TARGET_IP, TARGET_PORT))
```

**메서드**: `socket.sendto(data, address)`

**파라미터**:
- `data`: 바이트 배열 (UTF-8 인코딩 JSON)
- `address`: (IP, Port) 튜플

**인코딩**: `encode('utf-8')`
- 문자열 → 바이트
- UTF-8 인코딩 (국제 표준)
- JSON은 텍스트 형식이므로 필수

**주소**: `(TARGET_IP, TARGET_PORT)` = `("10.10.20.10", 10112)`

**프로토콜**: UDP (비연결형)
- 패킷 손실 가능
- 빠른 전송
- 오버헤드 최소

---

#### 7.1.8 Multiplexer 전송 (라인 64)

```python
# 2) Multiplexer로 전송 (Bridge Zone NMEA 변환용)
self.sock.sendto(message.encode('utf-8'), (MULTIPLEXER_IP, MULTIPLEXER_PORT))
```

**차이점**: 주소만 다름
- Control Zone: `10.10.20.10:10112`
- Multiplexer: `127.0.0.1:10113`

**같은 소켓 사용**: `self.sock` 재사용

**같은 메시지**: 동일한 JSON 데이터 전송

---

#### 7.1.9 로그 출력 (라인 66-70)

```python
print(f"[SENT] Engine: RPM={sensor_data['engine']['rpm']:.0f}, Temp={sensor_data['engine']['temperature']:.1f}°C, Oil={sensor_data['engine']['oil_pressure']:.2f}bar, Load={sensor_data['engine']['load']:.1f}%")
print(f"       Fuel: Level={sensor_data['fuel']['level']:.1f}%, Flow={sensor_data['fuel']['consumption_rate']:.2f}L/h, Temp={sensor_data['fuel']['temperature']:.1f}°C")
print(f"       Cooling: Temp={sensor_data['cooling']['temperature']:.1f}°C, Pressure={sensor_data['cooling']['pressure']:.2f}bar")
print(f"       Electrical: Battery={sensor_data['electrical']['battery_voltage']:.2f}V")
print(f"       Navigation: Rudder={sensor_data['navigation']['rudder_angle']:.1f}°, Depth={sensor_data['navigation']['water_depth']:.1f}m")
```

**포맷 지정자**:
- `:.0f`: 소수점 0자리 (정수)
- `:.1f`: 소수점 1자리
- `:.2f`: 소수점 2자리

**출력 예시**:
```
[SENT] Engine: RPM=850, Temp=85.0°C, Oil=4.50bar, Load=60.0%
       Fuel: Level=75.0%, Flow=12.50L/h, Temp=35.0°C
       Cooling: Temp=82.0°C, Pressure=1.80bar
       Electrical: Battery=24.50V
       Navigation: Rudder=0.0°, Depth=50.0m
```

**들여쓰기**: 공백 7개로 정렬
- 가독성 향상
- 그룹별 구분

---

#### 7.1.10 센서 값 업데이트 (라인 73)

```python
# 센서 값 업데이트
self.update_sensors()
```

**호출 메서드**: `update_sensors()`

**역할**: 다음 주기를 위한 센서 값 변경

**알고리즘**: Random Walk

**타이밍**: 전송 후 업데이트 (다음 주기 준비)

---

#### 7.1.11 2초 대기 (라인 75)

```python
time.sleep(2)  # 2초마다 전송
```

**함수**: `time.sleep(seconds)`

**파라미터**: 2 (초)

**효과**:
- 2초 동안 프로그램 일시 정지
- CPU 사용률 절감
- 주기적 전송 구현

**주기 계산**:
- 1분: 30회 전송
- 1시간: 1800회 전송
- 1일: 43200회 전송

---

#### 7.1.12 KeyboardInterrupt 처리 (라인 77-79)

```python
except KeyboardInterrupt:
    print("\n[Sensor Simulator] Shutting down...")
    break
```

**예외**: `KeyboardInterrupt`

**발생**: Ctrl+C 입력 시

**처리**:
1. 종료 메시지 출력
2. `break`로 while 루프 탈출

**개행 문자**: `\n`으로 ^C 다음 줄에 출력

---

#### 7.1.13 일반 예외 처리 (라인 80-81)

```python
except Exception as e:
    print(f"[Sensor Simulator] Error: {e}")
```

**예외**: 모든 Exception

**포착 대상**:
- 네트워크 에러
- JSON 직렬화 에러
- 기타 런타임 에러

**처리**: 에러 메시지 출력 후 계속 실행

**문제점**: 에러 발생해도 루프 계속 (무한 에러 로그 가능)

---

### 7.2 generate_sensor_data 메서드 (라인 80-109)

#### 7.2.1 메서드 시그니처

```python
def generate_sensor_data(self):
    """센서 데이터 생성"""
```

**파라미터**: 없음

**반환값**: dict (센서 데이터 구조)

**역할**: 현재 센서 상태를 JSON 구조로 변환

---

#### 7.2.2 알람 체크 (라인 82)

```python
# 알람 체크
self.check_alarms()
```

**순서**: 센서 데이터 생성 전 알람 체크

**이유**: 최신 알람 상태를 데이터에 포함하기 위함

---

#### 7.2.3 데이터 구조 생성 시작 (라인 84)

```python
return {
```

**구조**: Python dict

**직접 반환**: 계산 후 즉시 return

---

#### 7.2.4 타임스탬프 (라인 85)

```python
"timestamp": datetime.utcnow().isoformat(),
```

**함수 체인**:
1. `datetime.utcnow()`: 현재 UTC 시간 (datetime 객체)
2. `.isoformat()`: ISO 8601 문자열 변환

**출력 형식**: `"2025-12-19T14:23:45.123456"`

**형식 구성**:
- 날짜: `YYYY-MM-DD`
- 구분: `T`
- 시간: `HH:MM:SS.ffffff`
- 시간대: UTC (Z 표기 없음)

**왜 UTC?**:
- 시간대 문제 방지
- 국제 표준
- 로그 분석 용이

---

#### 7.2.5 엔진 데이터 (라인 86-91)

```python
"engine": {
    "rpm": round(self.engine_rpm, 1),
    "temperature": round(self.engine_temp, 1),
    "oil_pressure": round(self.engine_oil_pressure, 2),
    "load": round(self.engine_load, 1)
},
```

**round() 함수 사용**:
- `round(value, digits)`: 소수점 자릿수 제한

**자릿수 선택**:
- RPM: 1자리 (850.0)
- Temperature: 1자리 (85.0)
- Oil Pressure: 2자리 (4.50)
- Load: 1자리 (60.0)

**이유**:
- 센서 정밀도 반영
- 전송 데이터 크기 감소
- 가독성 향상

---

#### 7.2.6 연료 데이터 (라인 92-96)

```python
"fuel": {
    "level": round(self.fuel_level, 1),
    "consumption_rate": round(self.fuel_consumption, 2),
    "temperature": round(self.fuel_temp, 1)
},
```

**필드**:
- `level`: 75.0% (탱크 잔량)
- `consumption_rate`: 12.50 L/h (소비율)
- `temperature`: 35.0°C (연료 온도)

---

#### 7.2.7 냉각 데이터 (라인 97-100)

```python
"cooling": {
    "temperature": round(self.coolant_temp, 1),
    "pressure": round(self.coolant_pressure, 2)
},
```

**필드**:
- `temperature`: 82.0°C
- `pressure`: 1.80 bar

---

#### 7.2.8 전기 데이터 (라인 101-103)

```python
"electrical": {
    "battery_voltage": round(self.battery_voltage, 2)
},
```

**필드**:
- `battery_voltage`: 24.50V

**정밀도**: 0.01V (2자리)

---

#### 7.2.9 항해 데이터 (라인 104-107)

```python
"navigation": {
    "rudder_angle": round(self.rudder_angle, 1),
    "water_depth": round(self.water_depth, 1)
},
```

**필드**:
- `rudder_angle`: 0.0° (키 각도)
- `water_depth`: 50.0m (수심)

---

#### 7.2.10 알람 데이터 (라인 108)

```python
"alarms": self.alarms.copy()
```

**메서드**: `list.copy()`

**목적**: 얕은 복사 (Shallow Copy)

**이유**:
- 원본 리스트 보호
- 외부 수정 방지

**대안**: `self.alarms[:]` 또는 `list(self.alarms)`

---

### 7.3 update_sensors 메서드 (라인 111-156)

#### 7.3.1 메서드 시그니처

```python
def update_sensors(self):
    """센서 값 업데이트"""
```

**파라미터**: 없음

**반환값**: 없음

**역할**: 모든 센서 값을 다음 주기를 위해 업데이트

**알고리즘**: Random Walk with Bounds

---

#### 7.3.2 Random Walk 알고리즘

**일반 형태**:
```python
self.sensor_value += random.uniform(-delta, +delta)
self.sensor_value = max(min_value, min(max_value, self.sensor_value))
```

**구성 요소**:
1. **Random Step**: `random.uniform(-delta, +delta)`
2. **Bound Checking**: `max(min, min(max, value))`

**특징**:
- 이전 값 기준 변화
- 연속성 보장
- 범위 제한

---

#### 7.3.3 엔진 RPM 업데이트 (라인 113-114)

```python
# 엔진 RPM (±50)
self.engine_rpm += random.uniform(-50, 50)
self.engine_rpm = max(600, min(1200, self.engine_rpm))
```

**변화량**: ±50 RPM

**범위**: 600-1200 RPM

**예시**:
```
850.0 + 30.5 = 880.5
880.5 - 45.2 = 835.3
835.3 + 50.0 = 885.3 (계속 변화)
```

**Bound 적용**:
```python
# 만약 RPM이 1250이 되면
self.engine_rpm = min(1200, 1250) = 1200  # 상한 적용
self.engine_rpm = max(600, 1200) = 1200   # 변경 없음
```

---

#### 7.3.4 엔진 온도 업데이트 (라인 117-118)

```python
# 엔진 온도 (±2도)
self.engine_temp += random.uniform(-2, 2)
self.engine_temp = max(75, min(105, self.engine_temp))
```

**변화량**: ±2°C

**범위**: 75-105°C

**변화 예시**:
```
85.0 + 1.3 = 86.3
86.3 - 1.8 = 84.5
84.5 + 2.0 = 86.5
```

---

#### 7.3.5 오일 압력 업데이트 (라인 121-122)

```python
# 엔진 오일 압력 (±0.3 bar)
self.engine_oil_pressure += random.uniform(-0.3, 0.3)
self.engine_oil_pressure = max(3.0, min(6.0, self.engine_oil_pressure))
```

**변화량**: ±0.3 bar

**범위**: 3.0-6.0 bar

**정밀 변화**: 작은 델타로 안정적 변화

---

#### 7.3.6 엔진 부하 업데이트 (라인 125-126)

```python
# 엔진 부하 (±5%)
self.engine_load += random.uniform(-5, 5)
self.engine_load = max(30, min(95, self.engine_load))
```

**변화량**: ±5%

**범위**: 30-95%

---

#### 7.3.7 연료 레벨 업데이트 (라인 129-130)

```python
# 연료 레벨 (서서히 감소)
self.fuel_level -= self.fuel_consumption / 1000
self.fuel_level = max(10, min(100, self.fuel_level))
```

**특별점**: **랜덤 아님, 일정하게 감소**

**감소량**: `self.fuel_consumption / 1000`

**계산**:
```python
# fuel_consumption = 12.5 L/h
감소량 = 12.5 / 1000 = 0.0125% (2초마다)

# 1분 (30회)
감소량 = 0.0125 * 30 = 0.375%

# 1시간 (1800회)
감소량 = 0.0125 * 1800 = 22.5%
```

**결과**: 약 4시간 후 연료 0%

---

#### 7.3.8 연료 소비율 업데이트 (라인 133-134)

```python
# 연료 소비율 (±1 L/h)
self.fuel_consumption += random.uniform(-1, 1)
self.fuel_consumption = max(8, min(20, self.fuel_consumption))
```

**변화량**: ±1 L/h

**범위**: 8-20 L/h

**영향**: 연료 레벨 감소 속도에 직접 영향

---

#### 7.3.9 냉각수 온도 업데이트 (라인 137-138)

```python
# 냉각수 온도 (±1.5도)
self.coolant_temp += random.uniform(-1.5, 1.5)
self.coolant_temp = max(70, min(95, self.coolant_temp))
```

**변화량**: ±1.5°C

**범위**: 70-95°C

---

#### 7.3.10 냉각수 압력 업데이트 (라인 141-142)

```python
# 냉각수 압력 (±0.2 bar)
self.coolant_pressure += random.uniform(-0.2, 0.2)
self.coolant_pressure = max(1.0, min(2.5, self.coolant_pressure))
```

**변화량**: ±0.2 bar

**범위**: 1.0-2.5 bar

---

#### 7.3.11 배터리 전압 업데이트 (라인 145-146)

```python
# 배터리 전압 (±0.5V)
self.battery_voltage += random.uniform(-0.5, 0.5)
self.battery_voltage = max(22.0, min(28.0, self.battery_voltage))
```

**변화량**: ±0.5V

**범위**: 22-28V

---

#### 7.3.12 키 각도 업데이트 (라인 149-150)

```python
# 키 각도 (±10도)
self.rudder_angle += random.uniform(-10, 10)
self.rudder_angle = max(-35, min(35, self.rudder_angle))
```

**변화량**: ±10°

**범위**: -35° ~ +35°

**큰 변화**: 조타는 빠르게 변할 수 있음

---

#### 7.3.13 수심 업데이트 (라인 153-154)

```python
# 수심 (±5m)
self.water_depth += random.uniform(-5, 5)
self.water_depth = max(10, min(200, self.water_depth))
```

**변화량**: ±5m

**범위**: 10-200m

---

### 7.4 check_alarms 메서드 (라인 158-200)

#### 7.4.1 메서드 시그니처

```python
def check_alarms(self):
    """알람 상태 체크"""
```

**파라미터**: 없음

**반환값**: 없음

**역할**: 센서 값 기준 알람 생성

---

#### 7.4.2 알람 리스트 초기화 (라인 159)

```python
self.alarms = []
```

**중요**: 매번 새로 생성

**이유**: 해제된 알람 자동 제거

**효과**: 현재 상태만 반영

---

#### 7.4.3 엔진 온도 알람 (라인 162-167)

```python
# 엔진 온도 경고
if self.engine_temp > 100:
    self.alarms.append({
        "level": "WARNING",
        "code": "ENG_TEMP_HIGH",
        "message": f"Engine temperature high: {self.engine_temp:.1f}°C"
    })
```

**조건**: `self.engine_temp > 100`

**임계값**: 100°C

**알람 레벨**: WARNING (높음)

**알람 코드**: `ENG_TEMP_HIGH`

**메시지 형식**: f-string으로 현재 값 포함

**예시 메시지**: `"Engine temperature high: 102.5°C"`

---

#### 7.4.4 오일 압력 알람 (라인 170-175)

```python
# 오일 압력 경고
if self.engine_oil_pressure < 3.5:
    self.alarms.append({
        "level": "WARNING",
        "code": "OIL_PRESS_LOW",
        "message": f"Engine oil pressure low: {self.engine_oil_pressure:.2f} bar"
    })
```

**조건**: `self.engine_oil_pressure < 3.5`

**임계값**: 3.5 bar

**알람 레벨**: WARNING

**알람 코드**: `OIL_PRESS_LOW`

---

#### 7.4.5 연료 레벨 알람 (라인 178-183)

```python
# 연료 레벨 경고
if self.fuel_level < 20:
    self.alarms.append({
        "level": "CAUTION",
        "code": "FUEL_LEVEL_LOW",
        "message": f"Fuel level low: {self.fuel_level:.1f}%"
    })
```

**조건**: `self.fuel_level < 20`

**임계값**: 20%

**알람 레벨**: CAUTION (중간)

**알람 코드**: `FUEL_LEVEL_LOW`

**차이**: WARNING보다 낮은 우선순위

---

#### 7.4.6 배터리 전압 알람 (라인 186-191)

```python
# 배터리 전압 경고
if self.battery_voltage < 23.0:
    self.alarms.append({
        "level": "CAUTION",
        "code": "BATTERY_LOW",
        "message": f"Battery voltage low: {self.battery_voltage:.2f}V"
    })
```

**조건**: `self.battery_voltage < 23.0`

**임계값**: 23.0V

**알람 레벨**: CAUTION

**알람 코드**: `BATTERY_LOW`

---

#### 7.4.7 수심 알람 (라인 194-199)

```python
# 수심 경고
if self.water_depth < 15:
    self.alarms.append({
        "level": "WARNING",
        "code": "SHALLOW_WATER",
        "message": f"Shallow water: {self.water_depth:.1f}m"
    })
```

**조건**: `self.water_depth < 15`

**임계값**: 15m

**알람 레벨**: WARNING (좌초 위험)

**알람 코드**: `SHALLOW_WATER`

---

## 8. 메인 실행 부분 분석

### 8.1 메인 블록 시작 (라인 202)

```python
if __name__ == "__main__":
```

**의미**: 직접 실행 시에만 아래 코드 실행

**동작**:
- `python sensor_sim.py`: 실행됨 ✅
- `import sensor_sim`: 실행 안 됨 ❌

**목적**: 모듈로 import 시 자동 실행 방지

---

### 8.2 argparse import (라인 203)

```python
import argparse
```

**위치**: 메인 블록 내부 import

**이유**:
- 모듈로 import 시 불필요
- 실행 시에만 필요
- 메모리 절약

---

### 8.3 ArgumentParser 생성 (라인 205)

```python
parser = argparse.ArgumentParser(description='Ship Sensor Simulator')
```

**클래스**: `argparse.ArgumentParser`

**파라미터**:
- `description`: 프로그램 설명 (help 출력 시 표시)

---

### 8.4 명령줄 인자 정의 (라인 206-209)

#### 8.4.1 target-ip 인자

```python
parser.add_argument('--target-ip', default="10.10.20.10",
                    help='Target IP address (default: 10.10.20.10)')
```

**인자명**: `--target-ip`

**타입**: 문자열 (기본)

**기본값**: `"10.10.20.10"`

**도움말**: `'Target IP address (default: 10.10.20.10)'`

**사용 예시**:
```bash
python sensor_sim.py --target-ip 192.168.1.100
```

---

#### 8.4.2 target-port 인자

```python
parser.add_argument('--target-port', type=int, default=10112,
                    help='Target port (default: 10112)')
```

**인자명**: `--target-port`

**타입**: `int` (명시적 지정)

**기본값**: `10112`

**도움말**: `'Target port (default: 10112)'`

**사용 예시**:
```bash
python sensor_sim.py --target-port 5000
```

---

### 8.5 인자 파싱 (라인 211)

```python
args = parser.parse_args()
```

**메서드**: `parser.parse_args()`

**반환값**: `Namespace` 객체

**내용**: 명령줄 인자 파싱 결과

**예시**:
```python
# python sensor_sim.py --target-ip 192.168.1.100
args.target_ip = "192.168.1.100"
args.target_port = 10112 (기본값)
```

---

### 8.6 전역 변수 오버라이드 (라인 213-215)

```python
# Override global TARGET_IP and TARGET_PORT
global TARGET_IP, TARGET_PORT
TARGET_IP = args.target_ip
TARGET_PORT = args.target_port
```

**global 선언**: 전역 변수 수정 허용

**효과**: 모듈 상단 전역 변수 값 변경

**흐름**:
```python
# 1. 모듈 로드 시
TARGET_IP = "10.10.20.10"
TARGET_PORT = 10112

# 2. 명령줄 인자 파싱
args.target_ip = "192.168.1.100"
args.target_port = 5000

# 3. 전역 변수 오버라이드
TARGET_IP = "192.168.1.100"
TARGET_PORT = 5000

# 4. SensorSimulator에서 사용
self.sock.sendto(..., (TARGET_IP, TARGET_PORT))
```

---

### 8.7 시뮬레이터 시작 (라인 217)

```python
SensorSimulator().start()
```

**실행 순서**:
1. `SensorSimulator()`: 객체 생성 (`__init__` 호출)
2. `.start()`: 메인 루프 시작

**블로킹**: 무한 루프이므로 여기서 프로그램 대기

**종료**: Ctrl+C로만 가능

---

## 9. 코드 실행 흐름

### 9.1 전체 실행 흐름도

```
┌─────────────────────────────────────────┐
│  프로그램 시작                           │
│  python sensor_sim.py --target-ip ...   │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  1. Import 문 실행                       │
│     - time, random, socket, json, datetime│
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  2. 전역 변수 초기화                     │
│     - TARGET_IP = "10.10.20.10"         │
│     - TARGET_PORT = 10112               │
│     - MULTIPLEXER_IP = "127.0.0.1"      │
│     - MULTIPLEXER_PORT = 10113          │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  3. SensorSimulator 클래스 정의         │
│     (메모리에 로드, 실행 아님)           │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  4. if __name__ == "__main__": 체크    │
│     → True (직접 실행)                  │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  5. argparse 설정                       │
│     - ArgumentParser 생성               │
│     - 인자 정의 (--target-ip, --target-port)│
│     - 인자 파싱 (args)                  │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  6. 전역 변수 오버라이드                 │
│     - TARGET_IP = args.target_ip        │
│     - TARGET_PORT = args.target_port    │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  7. SensorSimulator() 객체 생성         │
│     (__init__ 메서드 호출)              │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  __init__ 메서드 실행                    │
│  ┌──────────────────────────────────┐  │
│  │ 1. UDP 소켓 생성                  │  │
│  │ 2. 센서 초기값 설정 (12개)        │  │
│  │    - engine_rpm = 850.0           │  │
│  │    - engine_temp = 85.0           │  │
│  │    - ... (10개 더)                │  │
│  │ 3. alarms = []                    │  │
│  └──────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  8. .start() 메서드 호출                │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│  start() 메서드 실행                     │
│  ┌──────────────────────────────────┐  │
│  │ 1. 시작 메시지 출력               │  │
│  │ 2. while True: 무한 루프 시작    │  │
│  └──────────┬───────────────────────┘  │
│             │                           │
│             ↓                           │
│  ┌─────────────────────────────────┐   │
│  │  루프 1회 실행                   │   │
│  │  ┌──────────────────────────┐   │   │
│  │  │ 1. generate_sensor_data()│   │   │
│  │  │    ↓                      │   │   │
│  │  │    - check_alarms()       │   │   │
│  │  │    - dict 생성 및 반환    │   │   │
│  │  │                           │   │   │
│  │  │ 2. json.dumps()           │   │   │
│  │  │                           │   │   │
│  │  │ 3. sendto() × 2           │   │   │
│  │  │    - Control Zone         │   │   │
│  │  │    - Multiplexer          │   │   │
│  │  │                           │   │   │
│  │  │ 4. print() × 5            │   │   │
│  │  │    - 로그 출력             │   │   │
│  │  │                           │   │   │
│  │  │ 5. update_sensors()       │   │   │
│  │  │    - 12개 센서 값 업데이트 │   │   │
│  │  │                           │   │   │
│  │  │ 6. time.sleep(2)          │   │   │
│  │  │    - 2초 대기             │   │   │
│  │  └──────────────────────────┘   │   │
│  └─────────┬───────────────────────┘   │
│            │                            │
│            ↓                            │
│       (루프 반복)                        │
│            ↑                            │
│            └─────────────────────────┐  │
│                                      │  │
│  Ctrl+C 입력 시:                     │  │
│  ┌───────────────────────────────┐  │  │
│  │ KeyboardInterrupt 예외 발생    │  │  │
│  │ → "Shutting down..." 출력     │  │  │
│  │ → break로 루프 탈출            │  │  │
│  └───────────────────────────────┘  │  │
└─────────────────────────────────────┘  │
               │                          │
               ↓                          │
┌─────────────────────────────────────────┐
│  9. 프로그램 종료                        │
│     - 소켓 자동 해제                    │
│     - 프로세스 종료                     │
└─────────────────────────────────────────┘
```

---

### 9.2 타이밍 다이어그램

```
시간축 (2초 간격)
────────────────────────────────────────────────────>

T=0s:   객체 생성 → start() 호출 → 시작 메시지 출력

T=0s:   ┌─ 루프 1회차 ─┐
        │ generate_sensor_data()   (즉시)
        │ json.dumps()             (즉시)
        │ sendto() × 2             (< 1ms)
        │ print() × 5              (< 1ms)
        │ update_sensors()         (< 1ms)
        │ sleep(2)                 (2000ms)
        └──────────────────────────┘

T=2s:   ┌─ 루프 2회차 ─┐
        │ (동일한 과정)
        │ ...
        └──────────────────────────┘

T=4s:   ┌─ 루프 3회차 ─┐
        │ ...
        └──────────────────────────┘

...

T=Ctrl+C: KeyboardInterrupt → 종료
```

---

## 10. 코드 품질 및 개선점

### 10.1 현재 코드의 장점

#### 1. 명확한 구조
- 클래스 기반 설계
- 메서드별 역할 분리
- 독스트링 제공

#### 2. 확장성
- 새 센서 추가 용이
- 알람 조건 커스터마이징 가능
- 전송 대상 추가 쉬움

#### 3. 설정 유연성
- 명령줄 인자 지원
- 전역 변수로 중앙 관리

#### 4. 현실적 시뮬레이션
- Random Walk 알고리즘
- 범위 제한
- 적절한 변화율

---

### 10.2 개선 가능한 점

#### 1. 에러 처리 부족

**문제**:
```python
except Exception as e:
    print(f"[Sensor Simulator] Error: {e}")
    # 루프 계속 (무한 에러 가능)
```

**개선안**:
```python
except Exception as e:
    log.error(f"Error: {e}")
    error_count += 1
    if error_count > 10:
        log.critical("Too many errors, shutting down")
        break
    time.sleep(5)  # 에러 시 대기
```

---

#### 2. 소켓 리소스 관리

**문제**: 소켓 명시적 close() 없음

**개선안**:
```python
def start(self):
    try:
        # ... 메인 루프
    finally:
        self.sock.close()  # 항상 실행
        print("[Sensor Simulator] Socket closed")
```

---

#### 3. 로깅 시스템 미사용

**문제**: `print()` 사용

**개선안**:
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# 사용
log.info("[SENT] Engine: RPM=...")
```

---

#### 4. 설정 하드코딩

**문제**: 초기값, 범위가 코드에 하드코딩

**개선안**: 설정 파일 사용
```python
# config.json
{
  "sensors": {
    "engine_rpm": {
      "initial": 850.0,
      "min": 600,
      "max": 1200,
      "delta": 50
    }
  }
}
```

---

#### 5. 센서 상관관계 미반영

**문제**: 센서 독립적 변화 (비현실적)

**개선안**:
```python
# RPM 높으면 온도도 상승
if self.engine_rpm > 1000:
    self.engine_temp += 0.5  # 추가 상승

# 부하 높으면 연료 소비 증가
self.fuel_consumption = 8 + (self.engine_load / 10)
```

---

#### 6. 타임스탬프 정밀도

**문제**: microsecond 포함 (과도한 정밀도)

**개선안**:
```python
# 밀리초만 포함
datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
# 출력: "2025-12-19T14:23:45.123"
```

---

#### 7. 전송 실패 처리 없음

**문제**: `sendto()` 실패 시 무시

**개선안**:
```python
try:
    self.sock.sendto(message.encode('utf-8'), (TARGET_IP, TARGET_PORT))
except OSError as e:
    log.error(f"Failed to send to Control Zone: {e}")
    failed_sends += 1
```

---

#### 8. 알람 중복 체크 없음

**문제**: 같은 알람 반복 생성

**개선안**:
```python
# 알람 상태 추적
self.active_alarms = set()

# 새 알람만 추가
if "ENG_TEMP_HIGH" not in self.active_alarms:
    self.alarms.append(...)
    self.active_alarms.add("ENG_TEMP_HIGH")
```

---

#### 9. 주기 정확도 문제

**문제**: `sleep(2)` 외에 처리 시간 추가됨

**실제 주기**: 약 2.001-2.005초

**개선안**:
```python
next_run = time.time() + 2.0

while True:
    # ... 센서 처리

    # 정확한 주기 유지
    sleep_time = next_run - time.time()
    if sleep_time > 0:
        time.sleep(sleep_time)
    next_run += 2.0
```

---

#### 10. 단위 테스트 부재

**개선안**: pytest 사용
```python
# test_sensor_sim.py
def test_sensor_initialization():
    sim = SensorSimulator()
    assert sim.engine_rpm == 850.0
    assert 600 <= sim.engine_rpm <= 1200

def test_random_walk():
    sim = SensorSimulator()
    initial_rpm = sim.engine_rpm
    sim.update_sensors()
    assert sim.engine_rpm != initial_rpm
    assert 600 <= sim.engine_rpm <= 1200
```

---

## 부록

### A. 전체 코드 요약

```
총 라인 수: 220줄
- Import: 6줄
- 전역 변수: 6줄
- SensorSimulator 클래스: 182줄
  - __init__: 26줄
  - start: 32줄
  - generate_sensor_data: 30줄
  - update_sensors: 46줄
  - check_alarms: 43줄
- 메인 블록: 17줄
```

### B. 복잡도 분석

**Cyclomatic Complexity**:
- `__init__`: 1 (단순)
- `start`: 3 (중간)
- `generate_sensor_data`: 1 (단순)
- `update_sensors`: 1 (단순)
- `check_alarms`: 6 (약간 복잡)

**전체 평가**: 낮은 복잡도, 유지보수 용이

---

**문서 버전**: 1.0
**작성일**: 2025-12-19
**작성자**: Technical Documentation Team
**대상 독자**: Python 개발자, 시스템 엔지니어
