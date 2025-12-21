# rules/s3_1_sensor_replay.py
import hashlib
import json
import socket
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple
from rules import notify_hmi
from rules.actions import action_mark_data_invalid, action_hmi_banner

def _extract_ts(payload: Dict[str, Any], fields) -> Optional[float]:
    for k in fields:
        if k not in payload:
            continue
        v = payload.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None

class S3_1_SensorReplayWatcher:
    """
    UDP 10112 센서값에서 replay/stale 패턴 탐지
    - 동일 payload 반복(해시) N회
    - (가능시) timestamp 정체

    개선:
    - 기본은 soft 대응: 데이터 invalid 마킹 + trust score 감소
    - trust 임계 이하에서만 차단(옵션)
    - 샘플링 강등(표현) 포함
    """
    def __init__(self, cfg, ros, cooldown):
        self.cfg = cfg
        self.ros = ros
        self.cooldown = cooldown

        s = cfg.s3_1_sensor_replay or {}
        self.enabled = bool(s.get("enabled", True))
        self.bind_ip = str(s.get("bind_ip", "0.0.0.0"))
        self.port = int(s.get("sensor_port", 10112))

        self.window_sec = int(s.get("window_sec", 20))
        self.repeat_threshold = int(s.get("repeat_threshold", 10))
        self.stale_ts_threshold_sec = int(s.get("stale_ts_threshold_sec", 6))
        self.timestamp_fields = list(s.get("timestamp_fields", ["timestamp", "ts", "time"]))

        # soft 대응 기본
        self.invalid_ttl_sec = int(s.get("invalid_ttl_sec", 30))
        self.block_on_low_trust = bool(s.get("block_on_low_trust", False))
        self.low_trust_threshold = float(s.get("low_trust_threshold", 0.3))
        self.ip_block_duration_sec = int(s.get("ip_block_duration_sec", 180))

        # trust score
        self.trust_init = float(s.get("trust_init", 1.0))
        self.trust_decay = float(s.get("trust_decay", 0.25))      # 탐지 시 감소량
        self.trust_recover = float(s.get("trust_recover", 0.02))  # 정상 수신 시 회복량(루프당)
        self.trust: Dict[str, float] = {}

        # sampling degrade 표현용
        self.degrade_notice_sec = int(s.get("degrade_notice_sec", 10))

        # (recv_time, src_ip, hash, extracted_ts)
        self.hist: Deque[Tuple[float, str, str, Optional[float]]] = deque(maxlen=1000)

    def _purge(self, now: float):
        while self.hist and (now - self.hist[0][0] > self.window_sec):
            self.hist.popleft()

    def _hash(self, raw: bytes) -> str:
        return hashlib.sha256(raw).hexdigest()

    def _repeat_count(self, src_ip: str, h: str) -> int:
        return sum(1 for _, s, hh, _ in self.hist if s == src_ip and hh == h)

    def _timestamp_stale(self, src_ip: str) -> bool:
        samples = [(t, ts) for t, s, _, ts in self.hist if s == src_ip and ts is not None]
        if len(samples) < 2:
            return False
        first_t, first_ts = samples[0]
        last_t, last_ts = samples[-1]
        if abs(last_ts - first_ts) < 1e-9 and (last_t - first_t) >= self.stale_ts_threshold_sec:
            return True
        return False

    def _get_trust(self, src_ip: str) -> float:
        return self.trust.get(src_ip, self.trust_init)

    def _set_trust(self, src_ip: str, v: float):
        self.trust[src_ip] = max(0.0, min(1.0, v))

    def _detect(self, src_ip: str, reason: str, evidence: Dict[str, Any]):
        if src_ip in self.cfg.benign_sources:
            print(f"[S3_1] {src_ip} benign, ignore.")
            return

        # trust 감소
        t0 = self._get_trust(src_ip)
        t1 = t0 - self.trust_decay
        self._set_trust(src_ip, t1)

        # ✅ soft 대응: 데이터 invalid 마킹
        if self.cooldown.ok_notify(f"s3_1_invalid:{src_ip}:{reason}", self.cfg.notify_cooldown_sec):
            action_mark_data_invalid(
                self.cfg,
                source="SENSOR",
                src_ip=src_ip,
                ttl_sec=self.invalid_ttl_sec,
                reason=reason,
                evidence={"trust": t1, **evidence}
            )
            action_hmi_banner(
                self.cfg,
                text="⚠ SENSOR DATA MAY BE STALE/REPLAY. Marked INVALID (soft response).",
                level="warn",
                ttl_sec=self.invalid_ttl_sec,
                extra={"src_ip": src_ip, "reason": reason, "trust": t1}
            )

        # (선택) low trust면 차단
        blocked = False
        if self.block_on_low_trust and t1 <= self.low_trust_threshold:
            if self.cooldown.ok_block(f"s3_1_block:{src_ip}", self.cfg.block_cooldown_sec):
                self.ros.block_ip(src_ip, timeout_sec=self.ip_block_duration_sec, comment="auto-block(S3_1 low-trust sensor)")
                blocked = True
                print(f"[S3_1] blocked(low-trust): {src_ip} trust={t1:.2f}")

        if self.cooldown.ok_notify(f"s3_1_notify:{src_ip}:{reason}", self.cfg.notify_cooldown_sec):
            notify_hmi(self.cfg, {
                "type": "S3_1_SENSOR_REPLAY_STALE",
                "description": "Sensor replay/stale detected (S3_1). Prefer data-trust response over network blocking.",
                "src_ip": src_ip,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                "reason": reason,
                "evidence": evidence,
                "trust_score": self._get_trust(src_ip),
                "mitigation": {
                    "data_invalidated": True,
                    "invalid_ttl_sec": self.invalid_ttl_sec,
                    "blocked": blocked,
                    "block_threshold": self.low_trust_threshold if self.block_on_low_trust else None,
                }
            })

    def run_forever(self):
        if not self.enabled:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.bind_ip, self.port))
        sock.settimeout(1.0)
        print(f"[S3_1] Listening UDP {self.bind_ip}:{self.port}")

        while True:
            try:
                raw, addr = sock.recvfrom(8192)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[S3_1] socket error: {e}")
                time.sleep(1)
                continue

            src_ip = addr[0]
            now = time.time()
            self._purge(now)

            h = self._hash(raw)
            ts = None
            try:
                obj = json.loads(raw.decode("utf-8", errors="ignore"))
                if isinstance(obj, dict):
                    ts = _extract_ts(obj, self.timestamp_fields)
            except Exception:
                pass

            self.hist.append((now, src_ip, h, ts))

            # 정상 수신이면 trust 회복(아주 조금)
            self._set_trust(src_ip, self._get_trust(src_ip) + self.trust_recover)

            # 1) repeat
            cnt = self._repeat_count(src_ip, h)
            if cnt >= self.repeat_threshold:
                self._detect(src_ip, "REPEAT_PAYLOAD", {
                    "count": cnt,
                    "threshold": self.repeat_threshold,
                    "window_sec": self.window_sec,
                    "hash": h
                })
                continue

            # 2) stale timestamp
            if self._timestamp_stale(src_ip):
                self._detect(src_ip, "STALE_TIMESTAMP", {
                    "threshold_sec": self.stale_ts_threshold_sec,
                    "window_sec": self.window_sec
                })
                continue
