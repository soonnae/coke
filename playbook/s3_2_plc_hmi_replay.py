# rules/s3_2_plc_hmi_replay.py
import time
from typing import Any, Dict, Optional
from rules import notify_hmi, http_get_json
from rules.actions import action_hmi_banner, action_hmi_set_readonly, action_hmi_require_ack

class S3_2_PlcHmiReplayWatcher:
    """
    PLC truth는 변하는데 HMI view가 정체되면 stale/replay로 판단 (S3_2)

    개선:
    - View Degradation 경고(배너)
    - HMI Read-only 강제
    - Operator ACK 요구(조작 잠금/승인)
    """
    def __init__(self, cfg, ros, cooldown):
        self.cfg = cfg
        self.ros = ros
        self.cooldown = cooldown

        s = cfg.s3_2_plc_hmi_replay or {}
        self.enabled = bool(s.get("enabled", False))
        self.interval_sec = int(s.get("interval_sec", 2))
        self.duration_sec = int(s.get("duration_sec", 6))

        self.plc_http_url = str(s.get("plc_http_url", "")).strip()
        self.hmi_http_url = str(s.get("hmi_http_url", "")).strip()
        self.stale_key = str(s.get("stale_key", "rpm"))
        self.require_plc_change = bool(s.get("require_plc_change", True))

        # 대응 옵션
        self.readonly_on_detect = bool(s.get("readonly_on_detect", True))
        self.ack_on_detect = bool(s.get("ack_on_detect", True))
        self.banner_ttl_sec = int(s.get("banner_ttl_sec", 15))

        self._hmi_last_value: Optional[float] = None
        self._hmi_stale_since: Optional[float] = None
        self._plc_changed_during_stale: bool = False
        self._plc_last_value: Optional[float] = None

    def _to_float(self, v) -> Optional[float]:
        try:
            return float(v)
        except Exception:
            return None

    def run_forever(self):
        if not self.enabled:
            return
        if not self.plc_http_url or not self.hmi_http_url:
            print("[S3_2] enabled=true but plc_http_url/hmi_http_url missing.")
            return

        print(f"[S3_2] Watching PLC/HMI stale view (key={self.stale_key}, duration={self.duration_sec}s)")
        while True:
            plc = http_get_json(self.plc_http_url) or {}
            hmi = http_get_json(self.hmi_http_url) or {}

            plc_v = self._to_float(plc.get(self.stale_key))
            hmi_v = self._to_float(hmi.get(self.stale_key))
            now = time.time()

            if plc_v is None or hmi_v is None:
                time.sleep(self.interval_sec)
                continue

            # PLC change tracking
            if self._plc_last_value is not None and abs(plc_v - self._plc_last_value) > 1e-9:
                if self._hmi_stale_since is not None:
                    self._plc_changed_during_stale = True
            self._plc_last_value = plc_v

            # HMI stale detection
            if self._hmi_last_value is None:
                self._hmi_last_value = hmi_v
                self._hmi_stale_since = None
                time.sleep(self.interval_sec)
                continue

            if abs(hmi_v - self._hmi_last_value) < 1e-9:
                # still stale
                if self._hmi_stale_since is None:
                    self._hmi_stale_since = now
                    self._plc_changed_during_stale = False
                else:
                    if (now - self._hmi_stale_since) >= self.duration_sec:
                        # 판단
                        if (not self.require_plc_change) or self._plc_changed_during_stale:
                            reason = "HMI_STALE_WITH_PLC_CHANGE" if self._plc_changed_during_stale else "HMI_STALE"
                            incident_id = f"S3_2:{reason}:{self.stale_key}"

                            # 1) View Degradation 경고
                            if self.cooldown.ok_notify(f"s3_2:banner:{reason}", self.cfg.notify_cooldown_sec):
                                action_hmi_banner(
                                    self.cfg,
                                    text="⚠ Display may be stale (Loss of View suspected). Verify with PLC truth.",
                                    level="warn",
                                    ttl_sec=self.banner_ttl_sec,
                                    extra={
                                        "incident_id": incident_id,
                                        "key": self.stale_key,
                                        "plc_value": plc_v,
                                        "hmi_value": hmi_v
                                    }
                                )

                            # 2) Read-only 강제
                            if self.readonly_on_detect and self.cooldown.ok_notify("s3_2:readonly", self.cfg.notify_cooldown_sec):
                                action_hmi_set_readonly(self.cfg, True, reason="S3_2 Loss-of-View protection")

                            # 3) ACK 요구
                            if self.ack_on_detect and self.cooldown.ok_notify(f"s3_2:ack:{reason}", self.cfg.notify_cooldown_sec):
                                action_hmi_require_ack(
                                    self.cfg,
                                    incident_id=incident_id,
                                    message="Loss of View suspected. Operator acknowledgement required before any HMI control action."
                                )

                            # 로그/알림
                            if self.cooldown.ok_notify(f"s3_2_notify:{reason}", self.cfg.notify_cooldown_sec):
                                notify_hmi(self.cfg, {
                                    "type": "S3_2_PLC_HMI_REPLAY_STALE",
                                    "description": "PLC↔HMI replay/stale view suspected (S3_2). Applied view protection.",
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                                    "reason": reason,
                                    "key": self.stale_key,
                                    "plc_value": plc_v,
                                    "hmi_value": hmi_v,
                                    "plc_changed_during_stale": self._plc_changed_during_stale,
                                    "sources": {"plc": self.plc_http_url, "hmi": self.hmi_http_url},
                                    "mitigation": {
                                        "view_banner": True,
                                        "readonly_enforced": self.readonly_on_detect,
                                        "ack_required": self.ack_on_detect,
                                    }
                                })

            else:
                # HMI updated → reset stale
                self._hmi_last_value = hmi_v
                self._hmi_stale_since = None
                self._plc_changed_during_stale = False

            time.sleep(self.interval_sec)
