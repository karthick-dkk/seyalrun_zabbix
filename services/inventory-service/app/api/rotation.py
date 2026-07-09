"""Credential rotation policies + history + manual rotate trigger (v1.1 Feature 10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pydantic
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.servicetoken import mint

from ..config import get_settings
from ..database import get_session
from ..deps import require_admin, require_service_token
from ..models import ZACredential, ZACredentialHistory, ZACredentialHostLink, ZARotationPolicy
from ..schemas import CredentialHistoryOut, RotationPolicyIn

router = APIRouter(tags=["rotation"], dependencies=[Depends(require_service_token)])


async def _get_policy(session: AsyncSession, credential_id: str) -> ZARotationPolicy | None:
    res = await session.execute(select(ZARotationPolicy).where(ZARotationPolicy.credential_id == credential_id))
    return res.scalar_one_or_none()


def _policy_dict(policy: ZARotationPolicy | None, credential_id: str, default_days: int) -> dict:
    if policy is None:
        return {
            "id": None, "credential_id": credential_id, "rotation_days": default_days,
            "rotation_mode": "auto", "enabled": False,
            "last_rotated_at": None, "next_rotation_due": None,
        }
    return {
        "id": policy.id, "credential_id": policy.credential_id,
        "rotation_days": policy.rotation_days, "rotation_mode": policy.rotation_mode,
        "enabled": policy.enabled,
        "last_rotated_at": policy.last_rotated_at.isoformat() if policy.last_rotated_at else None,
        "next_rotation_due": policy.next_rotation_due.isoformat() if policy.next_rotation_due else None,
    }


@router.get("/credentials/{credential_id}/rotation-policy", dependencies=[Depends(require_admin)])
async def get_rotation_policy(credential_id: str, session: AsyncSession = Depends(get_session)):
    policy = await _get_policy(session, credential_id)
    return _policy_dict(policy, credential_id, get_settings().rotation_default_days)


@router.put("/credentials/{credential_id}/rotation-policy", dependencies=[Depends(require_admin)])
async def put_rotation_policy(
    credential_id: str,
    payload: RotationPolicyIn,
    session: AsyncSession = Depends(get_session),
):
    cred = await session.get(ZACredential, credential_id)
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credential not found")

    policy = await _get_policy(session, credential_id)
    base = cred.last_rotated_at or datetime.now(timezone.utc)
    next_due = base + timedelta(days=payload.rotation_days)

    if policy is None:
        policy = ZARotationPolicy(credential_id=credential_id)
        session.add(policy)
    policy.rotation_days = payload.rotation_days
    policy.rotation_mode = payload.rotation_mode
    policy.enabled = payload.enabled
    policy.last_rotated_at = cred.last_rotated_at
    policy.next_rotation_due = next_due
    await session.commit()
    await session.refresh(policy)
    return _policy_dict(policy, credential_id, get_settings().rotation_default_days)


@router.get("/credentials/{credential_id}/history", response_model=list[CredentialHistoryOut], dependencies=[Depends(require_admin)])
async def get_history(credential_id: str, session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(ZACredentialHistory)
        .where(ZACredentialHistory.credential_id == credential_id)
        .order_by(ZACredentialHistory.rotated_at.desc())
        .limit(20)
    )
    return res.scalars().all()


class _RotateIn(pydantic.BaseModel):
    template_id: str | None = None


@router.post("/credentials/{credential_id}/rotate", dependencies=[Depends(require_admin)])
async def rotate_now(
    credential_id: str,
    payload: _RotateIn,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
):
    """Trigger a rotate_secret job via automation-service. The executor pushes a new secret to the
    target hosts and calls back PUT /internal/credentials/{id}/secret, which archives history."""
    cred = await session.get(ZACredential, credential_id)
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credential not found")

    settings = get_settings()
    host_rows = await session.execute(
        select(ZACredentialHostLink.host_id).where(ZACredentialHostLink.credential_id == credential_id)
    )
    host_ids = [h for (h,) in host_rows.all()]

    token = mint("inventory-service", "automation-service", settings.service_jwt_secret)
    template_id = payload.template_id
    async with httpx.AsyncClient(base_url=settings.automation_service_url, timeout=10) as client:
        if not template_id:
            try:
                r = await client.get("/api/v1/job-templates", headers={"X-Service-Token": token})
                if r.status_code == 200:
                    tmpls = [t for t in r.json() if t.get("action_type") == "rotate_secret" and t.get("enabled", True)]
                    if tmpls:
                        template_id = tmpls[0]["id"]
            except httpx.HTTPError:
                pass
        if not template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No rotate_secret job template configured in Automation",
            )
        try:
            run = await client.post(
                "/internal/job-runs",
                headers={"X-Service-Token": token},
                json={
                    "job_template_id": template_id,
                    "triggered_by": f"user:{actor_id or 'admin'}",
                    "params": {"subject_credential_id": credential_id},
                    "target_host_ids": host_ids,
                },
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"automation unreachable: {exc}") from exc

    if run.status_code not in (200, 202):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"automation dispatch failed ({run.status_code})")

    policy = await _get_policy(session, credential_id)
    if policy is not None:
        policy.next_rotation_due = datetime.now(timezone.utc) + timedelta(days=policy.rotation_days)
        await session.commit()

    return {"run_id": run.json().get("run_id"), "dispatched": True}
