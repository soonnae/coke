# rules/s1_nmea_spoofing.py
import time
from collections import deque
from typing import Any, Deque, Dict, Tuple

from rules.utils import notify_hmi, http_get_json
from rules.actions import action_hmi_banner, action_mark_data_invalid

_S1_HITS: Dict[str, Deque[float]] = {}


def _push_hit(src_ip: str, now: float, window_sec: int) -> int:
    dq = _S1_HITS.setdefault(src_ip, deque(maxlen=2000))
    dq.append(now)
    while dq and (now - dq[0] > window_sec):
        dq.popleft()
    return len(dq)


def _nav_cross_check(cfg: Any) -> Tuple[str, Dict[str, Any]]:
    s = getattr(cfg, "s1_nav_check", {}) or {}
    if not isinstance(s, dict):
        s = {}

    gps_url = str(s.get("gps_url", "")).strip()
    ais_url = str(s.get("ais_url", "")).strip()

    detail: Dict[str, Any] = {"gps_url": gps_url, "ais_url": ais_url}
    if not gps_url and not ais_url:
        return "unknown", detail

    gps = http_get_json(gps_url) if gps_url else None
    ais = http_get_json(ais_url) if ais_url else None
    detail["gps"] = gps
    detail["ais"] = ais

    gps_bad = bool(gps and gps.get("anomaly") is True)
    ais_bad = bool(ais and ais.get("anomaly") is True)

    if gps_bad and ais_bad:
        return "critical", detail
    if gps_bad and not ais_bad:
        return "suspect", detail
    if (not gps_bad) and ais_bad:
        return "suspect", detail
    return "unknown", detail


def handle_s1_nmea_spoofing(cfg: Any, ros: Any, cooldown: Any, event: Dict[str, Any]) -> None:
    src_ip = event.get("src_ip")
    alert = event.get("alert", {}) or {}
    sid = alert.get("signature_id")
    sig = alert.get("signature")

    if not src_ip:
        return

    if src_ip in getattr(cfg, "benign_sources", set()):
        print(f"[S1] {src_ip} benign, ignore.")
        return

    s1 = getattr(cfg, "s1_nmea_spoofing", {}) or {}
    if not isinstance(s1, dict):
        s1 = {}

    esc_window_sec = int(s1.get("escalation_window_sec", 5))
    esc_threshold = int(s1.get("escalation_threshold", 3))
    block_timeout = int(s1.get("block_timeout_sec", 180))

    now = time.time()
    hits = _push_hit(src_ip, now, esc_window_sec)

    severity, cross_detail = _nav_cross_check(cfg)

    # 1) notify
    if cooldown.ok_notify(f"s1_notify:{src_ip}", cfg.notify_cooldown_sec):
        notify_hmi(
            cfg,
            {
                "type": "NMEA_SPOOFING_DETECTED",
                "description": "NMEA spoofing detected. Apply trust-based handling (not hard block by default).",
                "src_ip": src_ip,
                "dest_ip": event.get("dest_ip"),
                "dest_port": event.get("dest_port"),
                "proto": event.get("proto"),
                "signature": sig,
                "signature_id": sid,
                "timestamp": event.get("timestamp"),
                "escalation": {
                    "window_sec": esc_window_sec,
                    "hits_in_window": hits,
                    "threshold": esc_threshold,
                },
                "trust_assessment": {
                    "severity": severity,
                    "cross_check": cross_detail,
                },
                "mitigation": {
                    "strategy": "escalation+trust",
                    "stage": "notify_only" if hits < esc_threshold else "escalated",
                    "ot_note": "Navigation attacks: prefer trust adjustment over blocking GPS feed.",
                },
            },
        )

    # 2) trust degrade
    if cooldown.ok_notify(f"s1_trust:{src_ip}:{severity}", cfg.notify_cooldown_sec):
        ttl = 15 if severity == "suspect" else 60 if severity == "critical" else 10

        action_mark_data_invalid(
            cfg,
            source="NAV",
            src_ip=src_ip,
            ttl_sec=ttl,
            reason=f"S1_NMEA_SPOOFING_{severity.upper()}",
            evidence={"hits_in_window": hits, "window_sec": esc_window_sec},
        )

        if severity in ("suspect", "critical"):
            action_hmi_banner(
                cfg,
                text=(
                    "⚠ Navigation data suspect: GPS/AIS trust degraded. Fallback to INS/Dead-Reckoning (logical)."
                    if severity == "suspect"
                    else " Navigation data critical: GPS+AIS inconsistent. Fallback to INS/Dead-Reckoning (logical)."
                ),
                level=("warn" if severity == "suspect" else "critical"),
                ttl_sec=ttl,
                extra={"src_ip": src_ip},
            )

    # 3) escalation block (with already-blocked skip)
    if hits >= esc_threshold:
        # 이미 차단된 IP면 재차단 시도 하지 않음
        is_blocked_fn = getattr(ros, "is_blocked_ip", None)
        if callable(is_blocked_fn) and is_blocked_fn(src_ip):
            print(f"[S1] escalation reached but already blocked, skip: {src_ip} hits={hits}/{esc_window_sec}s")
            return

        if cooldown.ok_block(f"s1:block:{src_ip}", cfg.block_cooldown_sec):
            ok = bool(ros.block_ip(src_ip, timeout_sec=block_timeout, comment="auto-block(S1 escalation NMEA spoofing)"))
            if ok:
                print(f"[S1] escalated block: {src_ip} hits={hits}/{esc_window_sec}s")
            else:
                print(f"[S1] escalated block FAILED: {src_ip} hits={hits}/{esc_window_sec}s")
