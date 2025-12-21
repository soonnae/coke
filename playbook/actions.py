# rules/actions.py
from typing import Any, Dict, Optional

from .utils import notify_hmi, http_post_json


def action_notify(cfg, payload: Dict[str, Any]) -> None:
    notify_hmi(cfg, payload)


def action_hmi_banner(
    cfg,
    text: str,
    level: str = "warn",
    ttl_sec: int = 10,
    extra: Optional[Dict[str, Any]] = None,
):
    """
    HMI에 배너/오버레이 표시 (Node-RED 대시보드 없으면 notify로 대체)
    """
    data = {
        "type": "HMI_BANNER",
        "level": level,
        "text": text,
        "ttl_sec": ttl_sec,
    }
    if extra:
        data.update(extra)
    notify_hmi(cfg, data)


def action_hmi_set_readonly(cfg, enabled: bool, reason: str):
    """
    HMI를 Read-only로 전환 (지원 엔드포인트가 없으면 notify로만 남김)
    """
    payload = {
        "type": "HMI_SET_READONLY",
        "enabled": bool(enabled),
        "reason": reason,
    }
    notify_hmi(cfg, payload)

    url = getattr(cfg, "hmi_control_url", "") or ""
    if url:
        http_post_json(url.rstrip("/") + "/read_only", payload)


def action_hmi_require_ack(cfg, incident_id: str, message: str):
    """
    운영자 확인(ACK) 요구 (락/승인 플로우는 Node-RED/웹에서 구현되었다고 가정)
    """
    payload = {
        "type": "HMI_REQUIRE_ACK",
        "incident_id": incident_id,
        "message": message,
    }
    notify_hmi(cfg, payload)

    url = getattr(cfg, "hmi_control_url", "") or ""
    if url:
        http_post_json(url.rstrip("/") + "/require_ack", payload)


def action_hmi_invalidate_session(cfg, subject: str, reason: str):
    """
    세션 무효화(로그아웃) 요청 (엔드포인트 없으면 notify로만)
    """
    payload = {
        "type": "HMI_INVALIDATE_SESSION",
        "subject": subject,
        "reason": reason,
    }
    notify_hmi(cfg, payload)

    url = getattr(cfg, "hmi_control_url", "") or ""
    if url:
        http_post_json(url.rstrip("/") + "/invalidate_session", payload)


def action_mark_data_invalid(
    cfg,
    source: str,
    src_ip: str,
    ttl_sec: int,
    reason: str,
    evidence: Dict[str, Any],
):
    """
    S3 계열: '네트워크 차단' 대신 '데이터 무효화(soft 대응)'를 표현
    """
    payload = {
        "type": "DATA_INVALIDATED",
        "source": source,  # "SENSOR" / "NAV" / "HMI"
        "src_ip": src_ip,
        "ttl_sec": ttl_sec,
        "reason": reason,
        "evidence": evidence,
    }
    notify_hmi(cfg, payload)

    # (선택) 실제 제어로직이 참조하는 “trust API”가 있다면 거기로 POST
    url = getattr(cfg, "trust_control_url", "") or ""
    if url:
        http_post_json(url.rstrip("/") + "/invalidate", payload)