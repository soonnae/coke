# rules/s2_modbus_attack.py
import time
from collections import deque
from typing import Any, Deque, Dict

from rules.utils import notify_hmi, http_post_json

# key: src_ip -> deque[timestamps]
_S2_HITS: Dict[str, Deque[float]] = {}


def _push(src_ip: str, now: float, window_sec: int) -> int:
    dq = _S2_HITS.setdefault(src_ip, deque(maxlen=5000))
    dq.append(now)
    while dq and (now - dq[0] > window_sec):
        dq.popleft()
    return len(dq)


def _try_safe_mode(cfg: Any, reason: str, detail: Dict[str, Any]) -> bool:
    """
    PLC 직접 차단 대신 Safe Mode 전환(개념).
    - cfg.s2_safe_mode.http_url 이 있으면 POST
    """
    s = getattr(cfg, "s2_safe_mode", {}) or {}
    if not isinstance(s, dict):
        s = {}

    url = str(s.get("http_url", "")).strip()
    if not url:
        return False

    payload = {"reason": reason, "detail": detail, "timestamp": time.time()}
    try:
        http_post_json(url, payload)
        return True
    except Exception:
        return False


def handle_s2_modbus_attack(cfg: Any, ros: Any, cooldown: Any, event: Dict[str, Any]) -> None:
    src_ip = event.get("src_ip")
    alert = event.get("alert", {}) or {}
    sid = alert.get("signature_id")
    sig = alert.get("signature")

    if not src_ip:
        return

    if src_ip in getattr(cfg, "benign_sources", set()):
        print(f"[S2] {src_ip} benign, ignore.")
        return

    m = getattr(cfg, "modbus_mitigation", {}) or {}
    if not isinstance(m, dict):
        m = {}

    enabled = bool(m.get("enabled", False))

    plc_ip = str(m.get("plc_ip", "10.10.40.10"))
    plc_port = int(m.get("plc_port", 502))
    suspects_list = str(m.get("modbus_suspects_list", "modbus_suspects"))

    # 빈도 기반 escalation
    window_sec = int(m.get("freq_window_sec", 5))
    suspect_threshold = int(m.get("suspect_threshold", 3))  # 5초 내 3회면 suspect
    block_threshold = int(m.get("block_threshold", 8))      # 5초 내 8회면 block

    ip_block_duration_sec = int(m.get("ip_block_duration_sec", 180))

    # “Write-only 차단” 정책 설치(가능하면) - 10분에 1번만 설치 시도
    if enabled and cooldown.ok_notify("s2_install_rules", 600):
        # RouterOSClient 구현에 따라 이 함수들이 존재한다고 가정
        ros.ensure_modbus_base_protection(
            suspects_list=suspects_list,
            plc_ip=plc_ip,
            plc_port=plc_port,
            rate_limit_pps=int(m.get("rate_limit_pps", 30)),
            rate_limit_burst=int(m.get("rate_limit_burst", 30)),
            rate_limit_time=str(m.get("rate_limit_time", "1s")),
            enable_write_only_block=bool(m.get("enable_write_only_block", True)),
        )

    now = time.time()
    hits = _push(src_ip, now, window_sec)

    action = "notify_only"
    stage = "normal"

    # suspect 단계: 전체 차단 대신 mark + write-only + rate-limit
    if hits >= suspect_threshold and enabled:
        stage = "suspect"
        if cooldown.ok_block(f"s2:mark:{src_ip}", cfg.block_cooldown_sec):
            ros.add_to_address_list(
                suspects_list,
                src_ip,
                timeout_sec=ip_block_duration_sec,
                comment="auto-mark(S2 modbus suspect)",
            )
            ros.enable_modbus_suspect_policy(
                suspects_list=suspects_list,
                plc_ip=plc_ip,
                plc_port=plc_port,
            )
            action = "mark_suspect+write_only_block+rate_limit"
            print(f"[S2] suspect policy applied: {src_ip} hits={hits}/{window_sec}s")

    # block 단계: escalation시 IP block
    if hits >= block_threshold and enabled:
        stage = "block"
        if cooldown.ok_block(f"s2:block:{src_ip}", cfg.block_cooldown_sec):
            ros.block_ip(
                src_ip,
                timeout_sec=ip_block_duration_sec,
                comment="auto-block(S2 modbus write/flood escalation)",
            )
            action = "ip_block"
            print(f"[S2] escalated block: {src_ip} hits={hits}/{window_sec}s")

    # Safe mode(개념) — suspect/block에서 선택적으로 시도
    safe_mode_ok = False
    if enabled and stage in ("suspect", "block"):
        if cooldown.ok_notify(f"s2:safe_mode:{stage}", 30):
            safe_mode_ok = _try_safe_mode(
                cfg,
                reason=f"S2_{stage.upper()}",
                detail={"src_ip": src_ip, "hits": hits, "window_sec": window_sec},
            )

    # HMI notify (쿨다운)
    if cooldown.ok_notify(f"s2_notify:{src_ip}", cfg.notify_cooldown_sec):
        notify_hmi(
            cfg,
            {
                "type": "MODBUS_WRITE_ATTACK_DETECTED",
                "description": "Modbus write anomaly detected. Prefer write-only containment to preserve monitoring availability.",
                "src_ip": src_ip,
                "dest_ip": event.get("dest_ip"),
                "dest_port": event.get("dest_port"),
                "proto": event.get("proto"),
                "app_proto": event.get("app_proto"),
                "signature": sig,
                "signature_id": sid,
                "timestamp": event.get("timestamp"),
                "escalation": {
                    "window_sec": window_sec,
                    "hits_in_window": hits,
                    "suspect_threshold": suspect_threshold,
                    "block_threshold": block_threshold,
                    "stage": stage,
                },
                "mitigation": {
                    "enabled": enabled,
                    "action": action,
                    "plc": f"{plc_ip}:{plc_port}",
                    "safe_mode_requested": safe_mode_ok,
                    "note": "Write-only containment keeps Read(0x03) monitoring alive.",
                },
            },
        )
