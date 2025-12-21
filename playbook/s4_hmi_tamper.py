# rules/s4_hmi_tamper.py
import hashlib
import json
import time
from typing import Any, Dict, Optional
from rules import notify_hmi, http_get_json
from rules.actions import action_hmi_invalidate_session, action_hmi_set_readonly, action_hmi_banner

class S4_HmiTamperWatcher:
    """
    S4: HMI 변조(불일치/조작) 탐지 + UI 무결성(해시) + 세션 무효화 + Read-only

    - PLC truth vs HMI view 값 불일치가 duration_sec 이상 지속되면 tamper
    - (추가) HMI 상태 해시가 갑자기 바뀌는 패턴을 integrity signal로 사용(데모용)
    """
    def __init__(self, cfg, ros, cooldown):
        self.cfg = cfg
        self.ros = ros
        self.cooldown = cooldown

        s = cfg.s4_hmi_tamper or {}
        self.enabled = bool(s.get("enabled", False))
        self.interval_sec = int(s.get("interval_sec", 2))
        self.duration_sec = int(s.get("duration_sec", 6))

        self.plc_http_url = str(s.get("plc_http_url", "")).strip()
        self.hmi_http_url = str(s.get("hmi_http_url", "")).strip()
        self.thresholds = dict(s.get("thresholds", {}) or {})

        # 신규: UI integrity hash
        self.enable_ui_hash = bool(s.get("enable_ui_hash", True))
        self.hash_keys = list(s.get("hash_keys", []))  # 비우면 전체 hmi json
        self._last_hmi_hash: Optional[str] = None

        # 대응 옵션
        self.readonly_on_detect = bool(s.get("readonly_on_detect", True))
        self.invalidate_session_on_detect = bool(s.get("invalidate_session_on_detect", True))
        self.banner_ttl_sec = int(s.get("banner_ttl_sec", 20))

        self._mismatch_since: Optional[float] = None
        self._last_detail: Optional[Dict[str, Any]] = None

    def _to_float(self, v) -> Optional[float]:
        try:
            return float(v)
        except Exception:
            return None

    def _diffs(self, plc: Dict[str, Any], hmi: Dict[str, Any]) -> Dict[str, Any]:
        diffs: Dict[str, Any] = {}
        for key, th in self.thresholds.items():
            pv = self._to_float(plc.get(key))
            hv = self._to_float(hmi.get(key))
            if pv is None or hv is None:
                continue
            thf = float(th)
            if abs(hv - pv) > thf:
                diffs[key] = {"plc": pv, "hmi": hv, "threshold": thf, "delta": hv - pv}
        return diffs

    def _hmi_hash(self, hmi: Dict[str, Any]) -> str:
        if self.hash_keys:
            subset = {k: hmi.get(k) for k in self.hash_keys}
            raw = json.dumps(subset, sort_keys=True, ensure_ascii=False).encode("utf-8")
        else:
            raw = json.dumps(hmi, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def run_forever(self):
        if not self.enabled:
            return
        if not self.plc_http_url or not self.hmi_http_url:
            print("[S4] enabled=true but plc_http_url/hmi_http_url missing.")
            return

        print(f"[S4] Integrity check started (duration={self.duration_sec}s)")
        while True:
            plc = http_get_json(self.plc_http_url) or {}
            hmi = http_get_json(self.hmi_http_url) or {}

            diffs = self._diffs(plc, hmi)
            now = time.time()

            # UI hash integrity signal (보조 증거)
            hash_changed = False
            hhash = None
            if self.enable_ui_hash:
                try:
                    hhash = self._hmi_hash(hmi)
                    if self._last_hmi_hash is not None and hhash != self._last_hmi_hash:
                        hash_changed = True
                    self._last_hmi_hash = hhash
                except Exception:
                    pass

            if diffs:
                if self._mismatch_since is None:
                    self._mismatch_since = now
                    self._last_detail = {"diffs": diffs, "hmi_hash": hhash, "hash_changed": hash_changed}

                if (now - self._mismatch_since) >= self.duration_sec:
                    incident_id = "S4:HMI_TAMPER"

                    if self.cooldown.ok_notify("s4:banner", self.cfg.notify_cooldown_sec):
                        action_hmi_banner(
                            self.cfg,
                            text="🚨 HMI view integrity compromised: PLC truth mismatch detected.",
                            level="critical",
                            ttl_sec=self.banner_ttl_sec,
                            extra={"incident_id": incident_id, "detail": self._last_detail}
                        )

                    # 1) Read-only 모드 전환
                    if self.readonly_on_detect and self.cooldown.ok_notify("s4:readonly", self.cfg.notify_cooldown_sec):
                        action_hmi_set_readonly(self.cfg, True, reason="S4 HMI integrity protection")

                    # 2) 세션 무효화(개념)
                    if self.invalidate_session_on_detect and self.cooldown.ok_notify("s4:invalidate", self.cfg.notify_cooldown_sec):
                        action_hmi_invalidate_session(self.cfg, subject="HMI_OPERATOR", reason="S4 suspected tampering")

                    if self.cooldown.ok_notify("s4:mismatch", self.cfg.notify_cooldown_sec):
                        notify_hmi(self.cfg, {
                            "type": "S4_HMI_TAMPER_DETECTED",
                            "description": "HMI tamper suspected (HMI view differs from PLC truth) (S4).",
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                            "detail": self._last_detail,
                            "sources": {"plc": self.plc_http_url, "hmi": self.hmi_http_url},
                            "mitigation": {
                                "readonly_enforced": self.readonly_on_detect,
                                "session_invalidated": self.invalidate_session_on_detect,
                                "ui_hash_signal": {"enabled": self.enable_ui_hash, "hash_changed": hash_changed, "hash": hhash},
                            }
                        })
            else:
                self._mismatch_since = None
                self._last_detail = None

            time.sleep(self.interval_sec)