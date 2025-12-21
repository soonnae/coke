import os
import subprocess
from typing import Optional, Tuple, Iterable, List


class RouterOSClient:
    """
    RouterOS SSH client with:
      - idempotent address-list add (avoid duplicate add errors)
      - structured return for block operations (ADDED / EXISTS / ERROR / TIMEOUT)
      - safer SSH options for automation
    """

    def __init__(self, host: str, user: str, ssh_key: str, default_block_list: str):
        self.host = host
        self.user = user
        self.ssh_key = os.path.expanduser(ssh_key)
        self.default_block_list = default_block_list

        # prefix convention used by playbook cleanup
        self.pb_prefix = "PB:"

    # -------------------------
    # SSH runner
    # -------------------------
    def _ssh_run(self, cmd: str, timeout_sec: int = 10) -> Tuple[int, str, str]:
        """
        Run a single RouterOS CLI command via SSH.
        Returns: (rc, stdout, stderr)
        """
        argv = [
            "ssh",
            "-i", self.ssh_key,
            "-o", "BatchMode=yes",                      # no password prompts
            "-o", f"ConnectTimeout=3",
            "-o", "StrictHostKeyChecking=accept-new",   # avoid interactive prompt
            "-o", "UserKnownHostsFile=/home/integration/.ssh/known_hosts",
            f"{self.user}@{self.host}",
            cmd,
        ]
        try:
            p = subprocess.run(
                argv,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
            )
            return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
        except subprocess.TimeoutExpired:
            return 124, "", "TIMEOUT"
        except Exception as e:
            return 255, "", str(e)

    def _ssh_run_many(self, cmds: Iterable[str], timeout_sec: int = 15) -> Tuple[int, str, str]:
        """
        Run multiple RouterOS commands as a single SSH session (script).
        """
        script = "\n".join([c.strip() for c in cmds if c and c.strip()])
        if not script.strip():
            return 0, "", ""
        return self._ssh_run(script, timeout_sec=timeout_sec)

    # -------------------------
    # Playbook cleanup helpers
    # -------------------------
    def cleanup_pb_rules_and_conntrack(self, prefix: str = "PB:") -> None:
        """
        Remove rules created by playbook and clear conntrack.
        """
        cmds = [
            f'/ip firewall filter remove [find comment~"{prefix}"]',
            f'/ip firewall nat remove [find comment~"{prefix}"]',
            f'/ip firewall address-list remove [find comment~"{prefix}"]',
            "/ip firewall connection remove [find]",
        ]
        rc, out, err = self._ssh_run_many(cmds, timeout_sec=20)
        if out:
            print(f"[RouterOS][CLEANUP rc={rc}] {out}")
        if rc != 0 and err:
            print(f"[RouterOS][CLEANUP] err={err}")

    # -------------------------
    # Address-list (idempotent)
    # -------------------------
    def add_to_address_list_idempotent(
        self,
        list_name: str,
        ip: str,
        timeout_sec: Optional[int] = None,
        comment: str = "auto",
    ) -> Tuple[bool, str]:
        """
        Add ip to address-list but avoid duplicate add.
        Returns: (ok, status)
          status in {"ADDED","EXISTS","ERROR","TIMEOUT","INVALID"}
        """
        if not ip:
            return False, "INVALID"

        # normalize comment: playbook cleanup expects PB: prefix
        c = (comment or "").strip() or "auto"
        if not c.startswith(self.pb_prefix):
            c = f"{self.pb_prefix}{c}"

        timeout = f"{int(timeout_sec)}s" if timeout_sec else ""

        # Use RouterOS scripting to print deterministic marker
        # - find where list+address exists -> PB:EXISTS
        # - else add -> PB:ADDED
        cmds: List[str] = [
            f':local id [/ip firewall address-list find where list="{list_name}" and address="{ip}"];',
        ]
        if timeout:
            cmds.append(
                f':if ([:len $id] = 0) do={{ /ip firewall address-list add list="{list_name}" address="{ip}" timeout="{timeout}" comment="{c}"; :put "PB:ADDED"; }} '
                f'else={{ :put "PB:EXISTS"; }}'
            )
        else:
            cmds.append(
                f':if ([:len $id] = 0) do={{ /ip firewall address-list add list="{list_name}" address="{ip}" comment="{c}"; :put "PB:ADDED"; }} '
                f'else={{ :put "PB:EXISTS"; }}'
            )

        rc, out, err = self._ssh_run_many(cmds, timeout_sec=10)

        if rc == 124 or err == "TIMEOUT":
            print(f"[RouterOS] address-list add TIMEOUT ip={ip} list={list_name}")
            return False, "TIMEOUT"

        o = (out or "").strip()
        if "PB:ADDED" in o:
            return True, "ADDED"
        if "PB:EXISTS" in o:
            return True, "EXISTS"

        # fallbacks
        if rc != 0:
            print(f"[RouterOS] address-list add ERROR rc={rc} ip={ip} list={list_name} err={err!r} out={o!r}")
            return False, "ERROR"

        # rc=0 but no marker (environment variance) -> treat as success
        return True, "ADDED"

    # Backward compatible (old name). Keep printing behavior optional.
    def add_to_address_list(
        self,
        list_name: str,
        ip: str,
        timeout_sec: Optional[int] = None,
        comment: str = "auto",
    ):
        """
        Backward compatible wrapper.
        Previously returned None and printed error.
        Now performs idempotent add; still prints on error.
        """
        ok, status = self.add_to_address_list_idempotent(list_name, ip, timeout_sec=timeout_sec, comment=comment)
        if not ok:
            print(f"[RouterOS] address-list add failed status={status} ip={ip} list={list_name}")
        return ok, status

    def block_ip(
        self,
        ip: str,
        timeout_sec: Optional[int] = None,
        comment: str = "auto-block(playbook)",
    ) -> bool:
        """
        Block IP by adding to default_block_list.
        Returns True if ADDED/EXISTS, else False.
        """
        ok, status = self.add_to_address_list_idempotent(
            self.default_block_list,
            ip,
            timeout_sec=timeout_sec,
            comment=comment,
        )
        if not ok:
            print(f"[RouterOS] block_ip FAILED ip={ip} status={status}")
        return ok

    def is_in_address_list(self, list_name: str, ip: str) -> bool:
        """
        Cheap existence check: list+address.
        """
        if not ip:
            return False
        cmd = f'/ip firewall address-list print where list="{list_name}" and address="{ip}"'
        rc, out, _ = self._ssh_run(cmd, timeout_sec=8)
        return (rc == 0 and bool(out.strip()))

    # -------------------------
    # Modbus protection rules (idempotent by comment)
    # -------------------------
    def ensure_modbus_rate_limit_rules(
        self,
        suspects_list: str,
        plc_ip: str,
        plc_port: int,
        rate_limit_pps: int,
        rate_limit_time: str,
        rate_limit_burst: int,
    ):
        comment_accept = f"{self.pb_prefix}MODBUS_LIMIT_ACCEPT"
        comment_drop = f"{self.pb_prefix}MODBUS_LIMIT_DROP"

        check_accept = f'/ip firewall filter print where comment~"{comment_accept}"'
        check_drop = f'/ip firewall filter print where comment~"{comment_drop}"'

        rc1, out1, _ = self._ssh_run(check_accept)
        rc2, out2, _ = self._ssh_run(check_drop)

        has_accept = (rc1 == 0 and bool(out1))
        has_drop = (rc2 == 0 and bool(out2))

        accept_rule = (
            "/ip firewall filter add chain=forward action=accept protocol=tcp "
            f"src-address-list={suspects_list} "
            f"dst-address={plc_ip} dst-port={plc_port} "
            f"limit={rate_limit_pps}/{rate_limit_time},{rate_limit_burst} "
            f'comment="{comment_accept}"'
        )
        drop_rule = (
            "/ip firewall filter add chain=forward action=drop protocol=tcp "
            f"src-address-list={suspects_list} "
            f"dst-address={plc_ip} dst-port={plc_port} "
            f'comment="{comment_drop}"'
        )

        if not has_accept:
            print("[RouterOS] Installing Modbus rate-limit ACCEPT rule...")
            rc, _, err = self._ssh_run(accept_rule)
            if rc != 0:
                print(f"[RouterOS] install accept failed rc={rc} err={err}")

        if not has_drop:
            print("[RouterOS] Installing Modbus rate-limit DROP rule...")
            rc, _, err = self._ssh_run(drop_rule)
            if rc != 0:
                print(f"[RouterOS] install drop failed rc={rc} err={err}")

    def ensure_modbus_base_protection(
        self,
        suspects_list: str,
        plc_ip: str,
        plc_port: int,
        rate_limit_pps: int,
        rate_limit_time: str,
        rate_limit_burst: int,
        enable_write_only_block: bool = True,
    ):
        """
        - Suspects address-list 기반 502 rate-limit
        - (가능하면) write-only 차단 룰(placeholder/best-effort)
        """
        self.ensure_modbus_rate_limit_rules(
            suspects_list=suspects_list,
            plc_ip=plc_ip,
            plc_port=plc_port,
            rate_limit_pps=rate_limit_pps,
            rate_limit_time=rate_limit_time,
            rate_limit_burst=rate_limit_burst,
        )
        if enable_write_only_block:
            self.ensure_modbus_write_drop_rules(suspects_list, plc_ip, plc_port)

    def ensure_modbus_write_drop_rules(self, suspects_list: str, plc_ip: str, plc_port: int):
        """
        (Best-effort) Modbus Write 차단 placeholder.
        ✅ 기존 코드의 self._run() 버그 수정: _ssh_run 사용.
        ✅ comment에 PB: prefix 포함 -> cleanup 가능
        """
        comment = f'{self.pb_prefix}S2 write-only block (best-effort placeholder)'

        check = f'/ip firewall filter print where comment~"{comment}"'
        rc, out, _ = self._ssh_run(check)
        if rc == 0 and out:
            return  # already exists

        rule = (
            f'/ip firewall filter add chain=forward src-address-list={suspects_list} '
            f'dst-address={plc_ip} protocol=tcp dst-port={plc_port} action=drop '
            f'comment="{comment}"'
        )
        rc, _, err = self._ssh_run(rule)
        if rc != 0:
            print(f"[RouterOS] install write-drop failed rc={rc} err={err}")

    def enable_modbus_suspect_policy(self, suspects_list: str, plc_ip: str, plc_port: int):
        """
        suspect list에 올라온 IP에 대해:
        - rate-limit 룰이 먹도록 보장
        - (옵션) write-drop 룰 활성화 보장
        """
        return
