# rules/pblog.py
import json, os, socket, threading, time, uuid
from datetime import datetime, timezone

_LOG_LOCK = threading.Lock()

def _iso_now():
    # Asia/Seoul이면 시스템 타임존이 +09:00일 가능성이 큼. 단순 now 사용
    return datetime.now().astimezone().isoformat(timespec="milliseconds")

class PlaybookLogger:
    def __init__(self, path: str, host_name: str | None = None, version: str = "0.1"):
        self.path = path
        self.host_name = host_name or socket.gethostname()
        self.version = version
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def emit(self, record: dict):
        record.setdefault("@timestamp", _iso_now())
        record.setdefault("component", "playbook")
        record.setdefault("host.name", self.host_name)
        record.setdefault("playbook.version", self.version)

        line = json.dumps(record, ensure_ascii=False)
        with _LOG_LOCK:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

def new_event_id() -> str:
    return str(uuid.uuid4())