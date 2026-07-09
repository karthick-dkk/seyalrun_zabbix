from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import log_action
from ..database import get_session
from ..deps import require_admin, require_service_token
from ..models import ZAAuthorization
from ..schemas import AuthorizationCreate, AuthorizationOut

router = APIRouter(
    prefix="/authorizations",
    tags=["authorizations"],
    dependencies=[Depends(require_service_token)],
)


@router.get("", response_model=list[AuthorizationOut])
async def list_authorizations(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZAAuthorization))
    return result.scalars().all()


def _merge(arr: list[str], scalar: str | None) -> list[str]:
    out = list(dict.fromkeys([*(arr or []), *( [scalar] if scalar else [])]))
    return out


def _apply(authz: ZAAuthorization, payload: AuthorizationCreate) -> None:
    """Fold legacy scalars + arrays into the many-to-many arrays, keeping the legacy
    scalar columns populated (first element) for back-compat readers."""
    users = _merge(payload.user_ids, payload.user_id)
    ugroups = _merge(payload.user_group_ids, payload.user_group_id)
    hosts = _merge(payload.host_ids, payload.host_id)
    hgroups = _merge(payload.host_group_ids, payload.host_group_id)

    if not users and not ugroups:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="at least one user or user group is required")
    if not hosts and not hgroups:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="at least one host or host group is required")

    authz.name = payload.name
    authz.user_ids, authz.user_group_ids = users, ugroups
    authz.host_ids, authz.host_group_ids = hosts, hgroups
    authz.user_id = users[0] if users else None
    authz.user_group_id = ugroups[0] if ugroups else None
    authz.host_id = hosts[0] if hosts else None
    authz.host_group_id = hgroups[0] if hgroups else None
    creds = _merge(payload.credential_ids, payload.credential_id)
    authz.credential_ids = creds
    authz.credential_id = creds[0] if creds else None
    authz.actions = payload.actions
    authz.date_start = payload.date_start
    authz.date_expired = payload.date_expired
    authz.enabled = payload.enabled


@router.post("", response_model=AuthorizationOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_authorization(
    payload: AuthorizationCreate,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    authz = ZAAuthorization()
    _apply(authz, payload)
    session.add(authz)
    await session.commit()
    await session.refresh(authz)

    await log_action(
        session, user_id=actor_id, username=actor_name or "", action="authorization.create",
        resource_type="authorization", resource_id=authz.id, details={"name": authz.name},
    )
    return authz


@router.put("/{authz_id}", response_model=AuthorizationOut, dependencies=[Depends(require_admin)])
async def update_authorization(
    authz_id: str,
    payload: AuthorizationCreate,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    result = await session.execute(select(ZAAuthorization).where(ZAAuthorization.id == authz_id))
    authz = result.scalar_one_or_none()
    if authz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="authorization not found")

    _apply(authz, payload)

    await session.commit()
    await session.refresh(authz)

    await log_action(
        session, user_id=actor_id, username=actor_name or "", action="authorization.update",
        resource_type="authorization", resource_id=authz.id,
    )
    return authz


@router.delete("/{authz_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_authorization(
    authz_id: str,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    result = await session.execute(select(ZAAuthorization).where(ZAAuthorization.id == authz_id))
    authz = result.scalar_one_or_none()
    if authz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="authorization not found")

    await session.delete(authz)
    await session.commit()

    await log_action(
        session, user_id=actor_id, username=actor_name or "", action="authorization.delete",
        resource_type="authorization", resource_id=authz_id,
    )
