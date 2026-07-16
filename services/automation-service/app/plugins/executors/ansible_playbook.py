"""Executor: run an Ansible playbook against target hosts."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import tempfile
import textwrap
from typing import Callable

import yaml

from libs.pluginbase import ActionExecutor, RunRequest, RunResult


def build_inventory(hosts: list, tmpdir: str) -> dict:
    """Build a YAML-safe Ansible inventory dict from (host, cred, sudo_pw) triples.

    Host address / username / password are attacker-or-vault-influenced strings. They are
    placed as STRUCTURED values so yaml.safe_dump escapes them — never hand-formatted into
    INI text, where a value with a space would inject extra inventory vars (e.g.
    ansible_ssh_common_args='-o ProxyCommand=...') and a newline would inject whole host
    entries. A synthetic host key (host_<id>) decouples the inventory name from the
    connection address so the address can never alter inventory structure. SSH key files
    are written into ``tmpdir``.

    sudo_pw (become password), same as the login password/key, only ever reaches this
    function already resolved from the credential vault — never a raw string sourced from
    job params — and lands in the inventory the same structured way, so it's yaml-escaped
    like everything else here.
    """
    inv_hosts: dict = {}
    for idx, (h, cred, sudo_pw) in enumerate(hosts):
        addr = h.get("ip") or h.get("ip_address") or h.get("hostname") or ""
        try:
            port = int(h.get("port") or h.get("ssh_port") or 22)
        except (TypeError, ValueError):
            port = 22
        hvars: dict = {"ansible_host": addr, "ansible_port": port}
        if cred:
            hvars["ansible_user"] = cred.get("username", "root")
            if cred.get("secret_type") == "password":
                hvars["ansible_ssh_pass"] = cred["secret"].get("password", "")
            elif cred.get("secret_type") == "ssh_key":
                key_path = os.path.join(tmpdir, f"key_{h.get('id', idx)}")
                with open(key_path, "w") as kf:
                    kf.write(cred["secret"].get("private_key", ""))
                os.chmod(key_path, stat.S_IRUSR)
                hvars["ansible_ssh_private_key_file"] = key_path
        if sudo_pw is not None:
            hvars["ansible_become"] = True
            hvars["ansible_become_method"] = "sudo"
            hvars["ansible_become_password"] = sudo_pw
        inv_hosts[f"host_{h.get('id', idx)}"] = hvars
    return {"all": {"children": {"targets": {"hosts": inv_hosts}}}}


class AnsiblePlaybookExecutor(ActionExecutor):
    name = "ansible_playbook"

    def validate(self, params: dict) -> None:
        # playbook_path was never actually read by execute() below — only
        # script_content ever ran — so it's not accepted as an alternative here.
        if not params.get("script_content"):
            raise ValueError("ansible_playbook requires script_content in params")

    async def execute(self, request: RunRequest, publish_line: Callable) -> RunResult:
        from app.config import get_settings
        import httpx
        from libs.servicetoken import mint

        settings = get_settings()

        if not request.target_host_ids:
            return RunResult(ok=False, output="no target_host_ids", exit_code=1)

        # Per-host credential resolution: per-host override → single shared credential →
        # the host's own linked credential ("default" = the push account of the server).
        host_cred_map = request.params.get("_host_credentials") or {}

        async def _resolve_cred(client, tok, cid):
            if not cid:
                return None
            cr = await client.get(f"/api/v1/internal/credentials/{cid}/secret",
                                  headers={"X-Service-Token": tok})
            return cr.json() if cr.status_code == 200 else None

        async def _resolve_login_cred(client, tok, hid):
            cid = host_cred_map.get(hid) or request.credential_id
            if not cid:
                rr = await client.get("/api/v1/credentials", params={"host_id": hid},
                                      headers={"X-Service-Token": tok})
                if rr.status_code == 200 and rr.json():
                    cid = rr.json()[0]["id"]
            return cid, await _resolve_cred(client, tok, cid)

        # Become/sudo password: sourced from the credential vault only, same discipline as
        # bash_script's sudo support — never a raw password sitting in job params, which
        # persist to za_job_runs and render in the Run Details UI. sudo_credential_id
        # overrides; else falls back to each host's own login credential (matching
        # Ansible's own ansible_become_password-defaults-to-ansible_password behavior),
        # which only works when that credential is password-type.
        use_sudo = bool(request.params.get("use_sudo"))
        sudo_credential_id = request.params.get("sudo_credential_id")

        hosts = []  # list of (host_dict, cred_dict|None, sudo_password|None)
        async with httpx.AsyncClient(base_url=settings.inventory_service_url, timeout=10) as client:
            tok = mint("automation-service", "inventory-service", settings.service_jwt_secret)
            shared_sudo_cred = await _resolve_cred(client, tok, sudo_credential_id) if sudo_credential_id else None
            for hid in request.target_host_ids:
                resp = await client.get(f"/api/v1/internal/hosts/{hid}", headers={"X-Service-Token": tok})
                if resp.status_code != 200:
                    continue
                login_cid, cred = await _resolve_login_cred(client, tok, hid)
                if not cred:
                    await publish_line(f"[host:{hid}] no credential available to connect — skipping host")
                    continue
                sudo_pw = None
                if use_sudo:
                    sudo_cred = shared_sudo_cred if sudo_credential_id else cred
                    if not sudo_cred or sudo_cred.get("secret_type") != "password":
                        await publish_line(f"[host:{hid}] use_sudo requires a password-type credential "
                                           f"— set sudo_credential_id to a password credential, skipping host")
                        continue
                    sudo_pw = sudo_cred.get("secret", {}).get("password", "")
                hosts.append((resp.json(), cred, sudo_pw))

        if not hosts:
            return RunResult(ok=False, output="could not resolve any target hosts", exit_code=1)

        playbook_content = request.params.get("script_content", "")
        if not playbook_content:
            await publish_line("[error] no playbook content")
            return RunResult(ok=False, output="no playbook content", exit_code=1)

        extra_vars = {k: v for k, v in request.params.items()
                      if k not in ("script_content", "run_local") and not k.startswith("_")}
        return await run_ansible_playbook(hosts, playbook_content, publish_line, extra_vars)

    async def run(self, request: RunRequest) -> RunResult:
        return await self.execute(request, lambda _: asyncio.sleep(0))


async def run_ansible_playbook(
    hosts: list,
    playbook_content: str,
    publish_line: Callable,
    extra_vars: dict | None = None,
) -> RunResult:
    """Shared subprocess dispatch — writes a YAML-safe inventory + the given
    playbook into a tempdir and runs `ansible-playbook` against it, streaming
    output via publish_line. Extracted from AnsiblePlaybookExecutor.execute()
    (pure move, same behavior) so the standalone connectivity-test endpoint
    (app/api/test_connection.py) can reuse this exact dispatch — tempdir
    scoping, read-only-rootfs-safe env vars, StrictHostKeyChecking=no — rather
    than re-implementing it a second time.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        inventory = build_inventory(hosts, tmpdir)
        inv_path = os.path.join(tmpdir, "inventory.yml")
        with open(inv_path, "w") as f:
            yaml.safe_dump(inventory, f, default_flow_style=False, allow_unicode=True)

        pb_path = os.path.join(tmpdir, "playbook.yml")
        with open(pb_path, "w") as f:
            f.write(playbook_content)

        cmd = [
            "ansible-playbook",
            "-i", inv_path,
            pb_path,
            # UserKnownHostsFile=/dev/null avoids writing ~/.ssh on the read-only
            # container FS. No BatchMode — it would disable sshpass password auth.
            "--ssh-common-args=-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        ]
        if extra_vars:
            cmd += ["--extra-vars", json.dumps(extra_vars)]

        await publish_line(f"[ansible] running playbook against {len(hosts)} host(s)...")
        # PYTHONUNBUFFERED=1 + ANSIBLE_STDOUT_CALLBACK=default forces line-buffered
        # stdout so each output line is published to Redis immediately rather than
        # being held until the subprocess exits.
        # The container runs read_only with only /tmp + /playbooks writable, so point
        # ansible's home/temp dirs at /tmp (else it fails creating ~/.ansible/tmp).
        ansible_home = os.path.join(tmpdir, ".ansible")
        proc_env = {
            **os.environ,
            "HOME": tmpdir,
            "PYTHONUNBUFFERED": "1",
            "ANSIBLE_FORCE_COLOR": "0",
            "ANSIBLE_STDOUT_CALLBACK": "default",
            "ANSIBLE_HOST_KEY_CHECKING": "False",
            "ANSIBLE_HOME": ansible_home,
            "ANSIBLE_LOCAL_TEMP": os.path.join(ansible_home, "tmp"),
            "ANSIBLE_PERSISTENT_CONTROL_PATH_DIR": os.path.join(ansible_home, "pc"),
        }
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=tmpdir,
            env=proc_env,
        )
        async for line in proc.stdout:
            await publish_line(line.decode().rstrip())
        await proc.wait()
        ok = proc.returncode == 0
        return RunResult(ok=ok, output="", exit_code=proc.returncode)
