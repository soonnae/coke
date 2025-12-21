# rules/runid.py
import time, uuid

_RUN_MAP = {}  # key -> (run_id, last_seen)

def get_run_id(key: str, ttl_sec: int = 600) -> str:
    now = time.time()
    # 청소
    dead = [k for k,(rid,ts) in _RUN_MAP.items() if now - ts > ttl_sec]
    for k in dead:
        _RUN_MAP.pop(k, None)

    if key in _RUN_MAP:
        rid, _ = _RUN_MAP[key]
        _RUN_MAP[key] = (rid, now)
        return rid

    rid = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    _RUN_MAP[key] = (rid, now)
    return rid