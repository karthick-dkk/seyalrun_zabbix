from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.deps import require_service_token, get_user_id, get_user_role
from app.models import ZAZabbixTriggerBinding

router = APIRouter(dependencies=[Depends(require_service_token)])


class BindingCreate(BaseModel):
    name: str
    job_template_id: str
    zabbix_triggerid: str | None = None
    zabbix_host_group: str | None = None
    severity_min: int = 0
    target_scope: str = "affected_host"
    post_result_to_zabbix: bool = True
    extra_vars: dict = {}
    enabled: bool = True


class BindingUpdate(BaseModel):
    name: str | None = None
    zabbix_triggerid: str | None = None
    zabbix_host_group: str | None = None
    severity_min: int | None = None
    target_scope: str | None = None
    post_result_to_zabbix: bool | None = None
    extra_vars: dict | None = None
    enabled: bool | None = None


class ManualTriggerPayload(BaseModel):
    binding_id: str
    host_id: str | None = None
    extra_params: dict = {}
    zbx_event_id: str | None = None   # when launched from a Zabbix Problem: post output back to it


@router.get("/trigger-bindings")
async def list_bindings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZAZabbixTriggerBinding).order_by(ZAZabbixTriggerBinding.created_at.desc()))
    return [_out(b) for b in result.scalars().all()]


@router.post("/trigger-bindings", status_code=status.HTTP_201_CREATED)
async def create_binding(
    payload: BindingCreate,
    role: str = Depends(get_user_role),
    session: AsyncSession = Depends(get_session),
):
    if role != "superadmin":
        raise HTTPException(status_code=403, detail="admin only")
    b = ZAZabbixTriggerBinding(**payload.model_dump())
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return _out(b)


@router.get("/trigger-bindings/{binding_id}")
async def get_binding(binding_id: str, session: AsyncSession = Depends(get_session)):
    b = await session.get(ZAZabbixTriggerBinding, binding_id)
    if b is None:
        raise HTTPException(status_code=404)
    return _out(b)


@router.put("/trigger-bindings/{binding_id}")
async def update_binding(
    binding_id: str,
    payload: BindingUpdate,
    role: str = Depends(get_user_role),
    session: AsyncSession = Depends(get_session),
):
    if role != "superadmin":
        raise HTTPException(status_code=403, detail="admin only")
    b = await session.get(ZAZabbixTriggerBinding, binding_id)
    if b is None:
        raise HTTPException(status_code=404)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(b, k, v)
    await session.commit()
    await session.refresh(b)
    return _out(b)


@router.delete("/trigger-bindings/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_binding(
    binding_id: str,
    role: str = Depends(get_user_role),
    session: AsyncSession = Depends(get_session),
):
    if role != "superadmin":
        raise HTTPException(status_code=403, detail="admin only")
    b = await session.get(ZAZabbixTriggerBinding, binding_id)
    if b is None:
        raise HTTPException(status_code=404)
    await session.delete(b)
    await session.commit()


@router.get("/triggers/resolve")
async def resolve_bindings(
    triggerid: str | None = None,
    severity: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """Bindings a Zabbix trigger can run — used by the console 'Run from Zabbix' view
    to show the operator which pre-bound playbook applies to a Problem. Returns
    trigger-id matches plus any-trigger (host-group / catch-all) bindings at or
    below this severity, so the operator confirms before running."""
    result = await session.execute(
        select(ZAZabbixTriggerBinding).where(ZAZabbixTriggerBinding.enabled.is_(True))
    )
    out = []
    for b in result.scalars().all():
        if severity and severity < b.severity_min:
            continue
        if b.zabbix_triggerid and triggerid and b.zabbix_triggerid != triggerid:
            continue
        out.append(_out(b))
    return out


@router.post("/triggers/manual", status_code=status.HTTP_202_ACCEPTED)
async def manual_trigger(
    payload: ManualTriggerPayload,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    from app.config import get_settings
    import httpx
    from libs.servicetoken import mint

    settings = get_settings()
    binding = await session.get(ZAZabbixTriggerBinding, payload.binding_id)
    if binding is None or not binding.enabled:
        raise HTTPException(status_code=404, detail="binding not found or disabled")

    target_host_ids = [payload.host_id] if payload.host_id else []
    run_params = {**binding.extra_vars, **payload.extra_params}

    async with httpx.AsyncClient(base_url=settings.automation_service_url, timeout=30) as client:
        tok = mint("zabbix-integration-service", "automation-service", settings.service_jwt_secret)
        resp = await client.post(
            "/api/v1/internal/job-runs",
            json={
                "job_template_id": binding.job_template_id,
                "triggered_by": f"manual_trigger:{binding.id}:{user_id}",
                "params": run_params,
                "target_host_ids": target_host_ids,
            },
            headers={"X-Service-Token": tok},
        )
        if resp.status_code not in (200, 202):
            raise HTTPException(status_code=502, detail=f"automation dispatch failed: {resp.text}")
        result = resp.json()

    # Launched from a Zabbix Problem (URL global script) → stream the full output
    # back onto that Problem, exactly like the auto/webhook paths do.
    run_id = result.get("run_id")
    if payload.zbx_event_id and run_id:
        import asyncio
        from app.api.webhook import _post_result_to_zabbix, _playbook_label
        playbook = await _playbook_label(binding, settings)
        asyncio.create_task(_post_result_to_zabbix(run_id, payload.zbx_event_id, settings,
                                                    header="▶ Manual remediation (console)",
                                                    playbook=playbook))
    return result


def _out(b: ZAZabbixTriggerBinding) -> dict:
    return {
        "id": b.id, "name": b.name, "job_template_id": b.job_template_id,
        "zabbix_triggerid": b.zabbix_triggerid, "zabbix_host_group": b.zabbix_host_group,
        "severity_min": b.severity_min, "target_scope": b.target_scope,
        "post_result_to_zabbix": b.post_result_to_zabbix, "extra_vars": b.extra_vars,
        "enabled": b.enabled,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }
