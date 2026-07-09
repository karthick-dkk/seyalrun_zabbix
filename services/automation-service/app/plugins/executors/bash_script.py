"""Executor: run a bash script locally or via SSH on target hosts."""

from __future__ import annotations

import asyncio
import os
import stat
import tempfile
from typing import Callable

from libs.pluginbase import ActionExecutor, RunRequest, RunResult

from app._ssh_exec import run_command as _ssh_run


class BashScriptExecutor(ActionExecutor):
    name = "bash_script"

    def validate(self, params: dict) -> None:
        if not params.get("script_content") and not params.get("inline_script"):
            raise ValueError("bash_script requires script_content in params or job template")

    async def execute(self, request: RunRequest, publish_line: Callable) -> RunResult:
        script = request.params.get("script_content") or request.params.get("inline_script", "")
        run_local = request.params.get("run_local", False)

        if not script:
            return RunResult(ok=False, output="no script_content provided", exit_code=1)

        if run_local or not request.target_host_ids:
            return await self._run_local(script, publish_line)

        results = []
        for host_id in request.target_host_ids:
            ok, out = await self._run_on_host(host_id, script, request, publish_line)
            results.append(ok)

        all_ok = all(results)
        return RunResult(ok=all_ok, output="", exit_code=0 if all_ok else 1)

    async def _run_local(self, script: str, publish_line: Callable) -> RunResult:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            tmp = f.name
        os.chmod(tmp, stat.S_IRWXU)
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", tmp,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in proc.stdout:
                text = line.decode().rstrip()
                await publish_line(text)
            await proc.wait()
            return RunResult(ok=(proc.returncode == 0), output="", exit_code=proc.returncode)
        finally:
            os.unlink(tmp)

    async def _run_on_host(self, host_id: str, script: str, request: RunRequest, publish_line: Callable) -> tuple[bool, str]:
        from app.config import get_settings
        import httpx

        settings = get_settings()
        await publish_line(f"[host:{host_id}] fetching host info...")

        host_cred_map = request.params.get("_host_credentials") or {}

        async with httpx.AsyncClient(base_url=settings.inventory_service_url, timeout=10) as client:
            from libs.servicetoken import mint
            tok = mint("automation-service", "inventory-service", settings.service_jwt_secret)
            resp = await client.get(f"/api/v1/internal/hosts/{host_id}", headers={"X-Service-Token": tok})
            if resp.status_code != 200:
                await publish_line(f"[host:{host_id}] host lookup failed: {resp.status_code}")
                return False, ""
            host = resp.json()

            # Credential: per-host override → single shared credential → host's linked
            # credential ("default" = the push account of the server).
            cred_id = host_cred_map.get(host_id) or request.credential_id
            if not cred_id:
                rr = await client.get("/api/v1/credentials", params={"host_id": host_id},
                                      headers={"X-Service-Token": tok})
                if rr.status_code == 200 and rr.json():
                    cred_id = rr.json()[0]["id"]
            if not cred_id:
                await publish_line(f"[host:{host_id}] no credential available to connect")
                return False, ""

            cred_resp = await client.get(f"/api/v1/internal/credentials/{cred_id}/secret", headers={"X-Service-Token": tok})
            if cred_resp.status_code != 200:
                await publish_line(f"[host:{host_id}] credential lookup failed")
                return False, ""
            cred = cred_resp.json()

        addr = host.get("ip") or host.get("ip_address") or host.get("hostname") or ""
        port = host.get("port") or host.get("ssh_port") or 22
        await publish_line(f"[host:{addr}] connecting...")
        exit_code, stdout, stderr = await _ssh_run(
            host=addr,
            port=port,
            username=cred.get("username", "root"),
            secret_type=cred.get("secret_type", "password"),
            secret=cred.get("secret", {}),
            command="bash -s",
            stdin_data=script,
        )
        for line in (stdout + stderr).splitlines():
            await publish_line(f"[host:{host_id}] {line}")
        return exit_code == 0, stdout

    async def run(self, request: RunRequest) -> RunResult:
        return await self.execute(request, lambda _: asyncio.sleep(0))
