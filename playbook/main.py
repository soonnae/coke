#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set, Iterable, List
import types

import yaml

from routeros.client import RouterOSClient
from rules.s1_nmea_spoofing import handle_s1_nmea_spoofing
from rules.s2_modbus_attack import handle_s2_modbus_attack
from rules.s3_1_sensor_replay import S3_1_SensorReplayWatcher
from rules.s3_2_plc_hmi_replay import S3_2_PlcHmiReplayWatcher
from rules.s4_hmi_tamper import S4_HmiTamperWatcher


CONFIG_PATH = os.environ.get("PLAYBOOK_CONFIG", "./config.yml")


# -------------------------
# Config
# -------------------------
@dataclass
class PlaybookConfig:
    eve_path: str

    # RouterOS
    routeros_host: str
    routeros_user: str
    routeros_ssh_key: str
    routeros_address_list: str

    # HMI
    hmi_enabled: bool
    hmi_url: str

    # Playbook
    nmea_spoofing_sids: Set[int]
    modbus_write_attack_sids: Set[int]
    sensor_replay_sids: Set[int]

    benign_sources: Set[str]
    never_block: Set[str]          # (3) allowlist 강제
    block_cooldown_sec: int
    notify_cooldown_sec: int

    modbus_mitigation: Dict[str, Any]

    s3_1_sensor_replay: Dict[str, Any]
    s3_2_plc_hmi_replay: Dict[str, Any]
    s4_hmi_tamper: Dict[str, Any]


def load_config(path: str) -> PlaybookConfig:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    suri = cfg.get("suricata", {})
    rtr = cfg.get("routeros", {})
    hmi = cfg.get("hmi", {})
    pb = cfg.get("playbook", {})

    return PlaybookConfig(
        eve_path=str(suri.get("eve_path", "/var/log/suricata/eve.json")),

        routeros_host=str(rtr.get("host", "10.10.20.1")),
        routeros_user=str(rtr.get("user", "admin")),
        routeros_ssh_key=str(rtr.get("ssh_key", "~/.ssh/id_rsa")),
        routeros_address_list=str(rtr.get("address_list", "blocked_attackers")),

        hmi_enabled=bool(hmi.get("enabled", False)),
        hmi_url=str(hmi.get("url", "http://10.10.10.10:1880/alert")),

        nmea_spoofing_sids=set(pb.get("nmea_spoofing_sids", []) or []),
        modbus_write_attack_sids=set(pb.get("modbus_write_attack_sids", []) or []),
        sensor_replay_sids=set(pb.get("sensor_replay_sids", []) or []),

        benign_sources=set(pb.get("benign_sources", []) or []),
        never_block=set(pb.get("never_block", []) or []),   # (3)
        block_cooldown_sec=int(pb.get("block_cooldown_sec", 120)),
        notify_cooldown_sec=int(pb.get("notify_cooldown_sec", 30)),

        modbus_mitigation=dict(pb.get("modbus_mitigation", {}) or {}),

        s3_1_sensor_replay=dict(pb.get("s3_1_sensor_replay", {}) or {}),
        s3_2_plc_hmi_replay=dict(pb.get("s3_2_plc_hmi_replay", {}) or {}),
        s4_hmi_tamper=dict(pb.get("s4_hmi_tamper", {}) or {}),
    )


# -------------------------
# RouterOS SSH helpers
# -------------------------
def _expand_path(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def routeros_ssh_run(host: str, user: str, ssh_key: str, commands: Iterable[str], timeout_sec: int = 10) -> str:
    """
    Run RouterOS CLI commands via SSH.
    - commands: list/iterable of RouterOS CLI lines
    """
    key_path = _expand_path(ssh_key)
    script = "\n".join([c.strip() for c in commands if c.strip()])
    if not script.strip():
        return ""

    # NOTE: RouterOS CLI accepts multi-line scripts over ssh
    cmd = [
        "ssh",
        "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=5",
        f"{user}@{host}",
        script,
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout_sec)
        return out
    except subprocess.CalledProcessError as e:
        # RouterOS sometimes returns non-zero for empty find/remove etc; still surface it
        return e.output or str(e)
    except subprocess.TimeoutExpired:
        return "[routeros_ssh_run] TIMEOUT"


def routeros_cleanup_pb(cfg: PlaybookConfig, pb_prefix: str = "PB:") -> None:
    """
    (1) 시작/종료 공통 cleanup
    - PB: comment 기반 filter/nat/address-list 제거
    - conntrack(connection) 제거
    """
    cmds = [
        f'/ip firewall filter remove [find comment~"{pb_prefix}"]',
        f'/ip firewall nat remove [find comment~"{pb_prefix}"]',
        f'/ip firewall address-list remove [find comment~"{pb_prefix}"]',
        "/ip firewall connection remove [find]",
    ]
    out = routeros_ssh_run(cfg.routeros_host, cfg.routeros_user, cfg.routeros_ssh_key, cmds, timeout_sec=15)
    if out.strip():
        print(f"[RouterOS][CLEANUP]\n{out}".rstrip())


def routeros_address_list_add_idempotent(
    cfg: PlaybookConfig,
    address: str,
    list_name: str,
    timeout_sec: int,
    comment: str,
) -> bool:
    """
    (4) idempotent: 같은 comment가 있으면 add 하지 않고 skip
    RouterOS에서:
      :local id [/ip firewall address-list find where comment="..."];
      :if ([:len $id] = 0) do={ /ip firewall address-list add ... }
    """
    t = f"{int(timeout_sec)}s"
    cmds = [
        f':local id [/ip firewall address-list find where comment="{comment}"];',
        f':if ([:len $id] = 0) do={{ /ip firewall address-list add list="{list_name}" address="{address}" timeout="{t}" comment="{comment}" }}',
    ]
    out = routeros_ssh_run(cfg.routeros_host, cfg.routeros_user, cfg.routeros_ssh_key, cmds, timeout_sec=10)
    # RouterOS는 add 성공해도 출력이 없을 수 있음. out로만 판별하기 어려워서 True 반환.
    # 단, SSH 자체 timeout이면 False
    if "[routeros_ssh_run] TIMEOUT" in out:
        print(f"[RouterOS] address-list add TIMEOUT (address={address}, comment={comment})")
        return False
    return True


# -------------------------
# Tail Suricata eve.json with stop
# -------------------------
def tail_eve_file(path: str, stop_event: threading.Event) -> Iterable[str]:
    proc = subprocess.Popen(
        ["tail", "-F", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        while not stop_event.is_set():
            line = proc.stdout.readline() if proc.stdout else ""
            if not line:
                time.sleep(0.1)
                continue
            yield line.strip()
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# -------------------------
# Cooldown
# -------------------------
class Cooldown:
    def __init__(self):
        self._block: Dict[str, float] = {}
        self._notify: Dict[str, float] = {}

    def ok_block(self, key: str, cooldown_sec: int) -> bool:
        now = time.time()
        last = self._block.get(key, 0.0)
        if now - last >= cooldown_sec:
            self._block[key] = now
            return True
        return False

    def ok_notify(self, key: str, cooldown_sec: int) -> bool:
        now = time.time()
        last = self._notify.get(key, 0.0)
        if now - last >= cooldown_sec:
            self._notify[key] = now
            return True
        return False


# -------------------------
# Safe wrapper: enforce (3) never_block and (4) idempotent
# -------------------------
def install_safe_routeros_wrappers(cfg: PlaybookConfig, ros: RouterOSClient) -> None:
    """
    rules/*.py가 ros.block_ip(...) 등을 호출하더라도,
    main에서 강제로 안전 정책을 적용:
      - never_block 강제
      - PB: comment 강제 + idempotent add
    """
    # 원본 메서드가 있으면 보관 (혹시 내부 구현이 더 좋을 수 있음)
    orig_block_ip = getattr(ros, "block_ip", None)

    def safe_block_ip(self, ip: str, timeout_sec: int = 180, comment: str = "") -> bool:
        # (3) never_block
        if ip in cfg.never_block:
            print(f"[RouterOS][SAFE] SKIP block (never_block): {ip}")
            return False

        # comment 정책 통일
        c = comment.strip() if comment else "auto-block"
        if not c.startswith("PB:"):
            c = f"PB:{c}"

        # (4) idempotent add: comment 기준 중복 방지
        ok = routeros_address_list_add_idempotent(
            cfg=cfg,
            address=ip,
            list_name=cfg.routeros_address_list,
            timeout_sec=timeout_sec,
            comment=c,
        )
        if ok:
            print(f"[RouterOS][SAFE] blocked via address-list: ip={ip} timeout={timeout_sec}s comment='{c}'")
        return ok

    # ros.block_ip를 강제 래핑
    if orig_block_ip is not None:
        ros._orig_block_ip = orig_block_ip  # type: ignore[attr-defined]

    ros.block_ip = types.MethodType(safe_block_ip, ros)  # type: ignore[assignment]
    print("[RouterOS][SAFE] Installed safe block_ip wrapper (never_block + idempotent + PB:comment).")


# -------------------------
# Event processing
# -------------------------
def process_eve_event(cfg: PlaybookConfig, ros: RouterOSClient, cd: Cooldown, event: Dict[str, Any]):
    if event.get("event_type") != "alert":
        return

    alert = event.get("alert", {}) or {}
    sid = alert.get("signature_id")
    if isinstance(sid, str) and sid.isdigit():
        sid = int(sid)

    if sid in cfg.nmea_spoofing_sids:
        handle_s1_nmea_spoofing(cfg, ros, cd, event)
        return

    if sid in cfg.modbus_write_attack_sids:
        handle_s2_modbus_attack(cfg, ros, cd, event)
        return

    # (옵션) sid 기반 sensor replay를 쓰고 싶으면 여기서 분기 가능 (현재는 watcher 기반)


def start_watchers(cfg: PlaybookConfig, ros: RouterOSClient, cd: Cooldown):
    threads = []

    if bool(cfg.s3_1_sensor_replay.get("enabled", True)):
        w = S3_1_SensorReplayWatcher(cfg, ros, cd)
        t = threading.Thread(target=w.run_forever, name="S3_1_SensorReplay", daemon=True)
        t.start()
        threads.append(t)
        print("[Playbook] S3_1 watcher started.")

    if bool(cfg.s3_2_plc_hmi_replay.get("enabled", False)):
        w = S3_2_PlcHmiReplayWatcher(cfg, ros, cd)
        t = threading.Thread(target=w.run_forever, name="S3_2_PlcHmiReplay", daemon=True)
        t.start()
        threads.append(t)
        print("[Playbook] S3_2 watcher started.")

    if bool(cfg.s4_hmi_tamper.get("enabled", False)):
        w = S4_HmiTamperWatcher(cfg, ros, cd)
        t = threading.Thread(target=w.run_forever, name="S4_HmiTamper", daemon=True)
        t.start()
        threads.append(t)
        print("[Playbook] S4 watcher started.")

    return threads


# -------------------------
# Main with (1)(2)
# -------------------------
def main():
    cfg = load_config(CONFIG_PATH)
    print("[Playbook] Starting playbook engine...")
    print(f"[Playbook] Config: {CONFIG_PATH}")
    print(f"[Playbook] Suricata EVE: {cfg.eve_path}")

    # (1) 시작 시 “이전 잔재 삭제” + conntrack 정리
    print("[Playbook] Pre-cleanup: removing previous PB:* rules and conntrack ...")
    routeros_cleanup_pb(cfg, pb_prefix="PB:")

    ros = RouterOSClient(
        host=cfg.routeros_host,
        user=cfg.routeros_user,
        ssh_key=cfg.routeros_ssh_key,
        default_block_list=cfg.routeros_address_list,
    )

    # (3)(4) main에서 강제로 안전 정책 적용
    install_safe_routeros_wrappers(cfg, ros)

    cd = Cooldown()
    start_watchers(cfg, ros, cd)

    stop_event = threading.Event()

    def _handle_stop(sig, frame):
        print(f"\n[Playbook] Signal received ({sig}). Stopping...")
        stop_event.set()

    # (2) Ctrl+C(SIGINT) / SIGTERM 받아도 finally에서 cleanup 되도록
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    try:
        for line in tail_eve_file(cfg.eve_path, stop_event=stop_event):
            if stop_event.is_set():
                break
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            try:
                process_eve_event(cfg, ros, cd, event)
            except Exception as e:
                print(f"[Playbook] Error processing event: {e}")

    finally:
        # (2) 종료 시 “무조건 원복”
        print("[Playbook] Cleanup on exit: removing PB:* rules and conntrack ...")
        try:
            routeros_cleanup_pb(cfg, pb_prefix="PB:")
        except Exception as e:
            print(f"[Playbook] Cleanup failed: {e}")

        print("[Playbook] Bye.")


if __name__ == "__main__":
    main()
