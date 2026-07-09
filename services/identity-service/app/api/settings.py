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
