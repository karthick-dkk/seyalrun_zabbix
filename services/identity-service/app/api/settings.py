"""Superadmin-editable settings (Zabbix integration URL/token).

- GET  /api/v1/settings/integration  (admin)      — redacted (token shown only as a bool)
- PUT  /api/v1/settings/integration  (superadmin)  — upsert; blank token keeps existing

The full token is only exposed to the gateway server-side via the internal endpoint
in api/internal.py (never to the browser).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import log_action
from ..database import get_session
from ..deps import require_admin, require_service_token, require_superadmin
from ..models import ZASetting

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_service_token)])

INTEGRATION_KEY = "integration"


class IntegrationSettingsIn(BaseModel):
    zabbix_console_url: str = ""
    zabbix_api_url: str = ""
    zabbix_api_token: str = ""  # blank = keep the existing token


async def get_integration_value(session: AsyncSession) -> dict:
    row = await session.get(ZASetting, INTEGRATION_KEY)
    return dict(row.value) if row and isinstance(row.value, dict) else {}


def _redacted(v: dict) -> dict:
    return {
        "zabbix_console_url": v.get("zabbix_console_url", ""),
        "zabbix_api_url": v.get("zabbix_api_url", ""),
        "zabbix_api_token_configured": bool(v.get("zabbix_api_token")),
    }


@router.get("/integration", dependencies=[Depends(require_admin)])
async def get_integration(session: AsyncSession = Depends(get_session)):
    return _redacted(await get_integration_value(session))


@router.put("/integration", dependencies=[Depends(require_superadmin)])
async def put_integration(
    payload: IntegrationSettingsIn,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    current = await get_integration_value(session)
    new = {
        "zabbix_console_url": payload.zabbix_console_url.strip(),
        "zabbix_api_url": payload.zabbix_api_url.strip(),
        # blank token = keep existing (never overwrite a set token with an empty one)
        "zabbix_api_token": payload.zabbix_api_token.strip() or current.get("zabbix_api_token", ""),
    }
    row = await session.get(ZASetting, INTEGRATION_KEY)
    if row is None:
        session.add(ZASetting(key=INTEGRATION_KEY, value=new))
    else:
        row.value = new
    await session.commit()
    await log_action(
        session, user_id=actor_id, username=actor_name or "", action="settings.update",
        resource_type="settings", resource_id=INTEGRATION_KEY,
        details={"zabbix_console_url": new["zabbix_console_url"], "zabbix_api_url": new["zabbix_api_url"],
                 "token_set": bool(new["zabbix_api_token"])},
    )
    return _redacted(new)


# ── Platform tunables + Zabbix-module trust settings (Zabbix embed feature) ──
#
# DB-backed overrides for a handful of SAFE, non-secret values — applied live
# by api-gateway's background settings cache (app/platform_settings.py), .env
# stays the fallback when no row exists yet. Real secrets (ZA_VAULT_PASSWORD,
# JWT_SECRET, SERVICE_JWT_SECRET, ZABBIX_MODULE_SECRET, DB_*, ...) are never
# accepted or returned by any endpoint in this file — changing them here would
# silently break decryption of every stored credential, so they stay .env-only.

PLATFORM_KEY = "platform"
ZABBIX_MODULE_KEY = "zabbix_module"


class PlatformSettingsIn(BaseModel):
    rate_limit_requests: int = 600
    rate_limit_window_seconds: int = 60
    session_idle_minutes: int = 30
    session_absolute_hours: int = 8
    log_level: str = "INFO"


class ZabbixModuleSettingsIn(BaseModel):
    enabled: bool = False
    trusted_ips: list[str] = []
    elevated_rate_limit: int = 5000


_PLATFORM_DEFAULTS = PlatformSettingsIn().model_dump()
_ZABBIX_MODULE_DEFAULTS = ZabbixModuleSettingsIn().model_dump()


async def _get_value(session: AsyncSession, key: str) -> dict:
    row = await session.get(ZASetting, key)
    return dict(row.value) if row and isinstance(row.value, dict) else {}


async def _put_value(session: AsyncSession, key: str, value: dict, actor_id: str | None, actor_name: str | None) -> None:
    row = await session.get(ZASetting, key)
    if row is None:
        session.add(ZASetting(key=key, value=value))
    else:
        row.value = value
    await session.commit()
    await log_action(
        session, user_id=actor_id, username=actor_name or "", action="settings.update",
        resource_type="settings", resource_id=key, details=value,
    )


@router.get("/platform", dependencies=[Depends(require_admin)])
async def get_platform(session: AsyncSession = Depends(get_session)):
    return {**_PLATFORM_DEFAULTS, **(await _get_value(session, PLATFORM_KEY))}


@router.put("/platform", dependencies=[Depends(require_superadmin)])
async def put_platform(
    payload: PlatformSettingsIn,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    # Bounded so a fat-fingered value can't lock everyone (including the editor)
    # out of the API or expire every session instantly.
    new = {
        "rate_limit_requests": max(10, min(payload.rate_limit_requests, 100_000)),
        "rate_limit_window_seconds": max(1, min(payload.rate_limit_window_seconds, 3600)),
        "session_idle_minutes": max(1, min(payload.session_idle_minutes, 1440)),
        "session_absolute_hours": max(1, min(payload.session_absolute_hours, 168)),
        "log_level": payload.log_level.upper() if payload.log_level.upper() in
            ("DEBUG", "INFO", "WARNING", "ERROR") else "INFO",
    }
    await _put_value(session, PLATFORM_KEY, new, actor_id, actor_name)
    return new


@router.get("/zabbix-module", dependencies=[Depends(require_admin)])
async def get_zabbix_module(session: AsyncSession = Depends(get_session)):
    return {**_ZABBIX_MODULE_DEFAULTS, **(await _get_value(session, ZABBIX_MODULE_KEY))}


@router.put("/zabbix-module", dependencies=[Depends(require_superadmin)])
async def put_zabbix_module(
    payload: ZabbixModuleSettingsIn,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    new = {
        "enabled": bool(payload.enabled),
        "trusted_ips": [ip.strip() for ip in payload.trusted_ips if ip.strip()],
        "elevated_rate_limit": max(10, min(payload.elevated_rate_limit, 1_000_000)),
    }
    await _put_value(session, ZABBIX_MODULE_KEY, new, actor_id, actor_name)
    return new
