from __future__ import annotations

import asyncio
import time

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.servicetoken import mint

from ..config import get_settings
from ..database import get_session
from ..deps import require_admin, require_service_token
from ..models import ZAHost, ZAHostGroupMember, ZAGateway, ZAZone
from ..schemas import GatewayCreate, GatewayOut, ZoneCreate, ZoneOut

router = APIRouter(tags=["zones"], dependencies=[Depends(require_service_token)])


async def require_admin_or_zone_authorized(
    zone_id: str,
    # X-User-Real-Role, NOT X-User-Role: the gateway "vouches" any capability-authorized
    # write up to X-User-Role: admin (rbac.downstream_role) so ordinary admin-gated CRUD
    # guards keep working unmodified for custom roles — but that means X-User-Role can't
    # tell a real admin from a vouched-for support write. X-User-Real-Role carries the
    # caller's actual role, which this resource-scoped check needs.
    role: str = Header(default="user", alias="X-User-Real-Role"),
    user_id: str = Header(default="", alias="X-User-Id"),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Zone *editing* (not create/delete) additionally opens to the 'support' role
    when they hold a za_authorization for at least one host in this zone — 'support'
    already has zones:PUT capability in the role matrix (libs.rbaccore), but isn't
    in the admin/superadmin authz-bypass set, so it needs this resource-scoped check
    same as every other resource action that role can reach. Mirrors how a user
    "manages" a zone today: by being authorized against the hosts inside it."""
    if role in ("admin", "superadmin"):
        return
    if role != "support" or not user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")

    settings = get_settings()
    tok = mint("inventory-service", "identity-service", settings.service_jwt_secret)
    async with httpx.AsyncClient(base_url=settings.identity_service_url, timeout=10) as client:
        resp = await client.get(
            "/api/v1/internal/authz/host-ids",
            params={"user_id": user_id, "strict": "true"},
            headers={"X-Service-Token": tok},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="could not resolve host authorization")
    data = resp.json()
    host_ids = set(data.get("host_ids") or [])
    group_ids = set(data.get("host_group_ids") or [])
    if group_ids:
        member_result = await session.execute(
            select(ZAHostGroupMember.host_id).where(ZAHostGroupMember.group_id.in_(group_ids))
        )
        host_ids.update(h for (h,) in member_result.all())
    if not host_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized for any host in this zone")

    count_result = await session.execute(
        select(ZAHost.id).where(ZAHost.zone_id == zone_id, ZAHost.id.in_(host_ids)).limit(1)
    )
    if count_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized for any host in this zone")


@router.get("/zones", response_model=list[ZoneOut])
async def list_zones(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZAZone))
    return result.scalars().all()


@router.post("/zones", response_model=ZoneOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_zone(payload: ZoneCreate, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(ZAZone).where(ZAZone.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="zone name already exists")
    zone = ZAZone(**payload.model_dump())
    session.add(zone)
    await session.commit()
    await session.refresh(zone)
    return zone


@router.put("/zones/{zone_id}", response_model=ZoneOut, dependencies=[Depends(require_admin_or_zone_authorized)])
async def update_zone(zone_id: str, payload: ZoneCreate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZAZone).where(ZAZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="zone not found")
    for field, value in payload.model_dump().items():
        setattr(zone, field, value)
    await session.commit()
    await session.refresh(zone)
    return zone


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_zone(zone_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZAZone).where(ZAZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="zone not found")
    await session.delete(zone)
    await session.commit()


@router.get("/internal/gateways/{gateway_id}", response_model=GatewayOut)
async def get_gateway_internal(gateway_id: str, session: AsyncSession = Depends(get_session)):
    """Direct gateway lookup by ID — called by terminal-service WS handler."""
    result = await session.execute(select(ZAGateway).where(ZAGateway.id == gateway_id))
    gw = result.scalar_one_or_none()
    if gw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="gateway not found")
    return gw


@router.get("/zones/{zone_id}/gateways", response_model=list[GatewayOut])
async def list_gateways(zone_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZAGateway).where(ZAGateway.zone_id == zone_id))
    return result.scalars().all()


@router.post("/zones/{zone_id}/gateways", response_model=GatewayOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_gateway(zone_id: str, payload: GatewayCreate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZAZone).where(ZAZone.id == zone_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="zone not found")
    data = payload.model_dump()
    data["zone_id"] = zone_id
    gateway = ZAGateway(**data)
    session.add(gateway)
    await session.commit()
    await session.refresh(gateway)
    return gateway


@router.put("/zones/{zone_id}/gateways/{gateway_id}", response_model=GatewayOut, dependencies=[Depends(require_admin)])
async def update_gateway(zone_id: str, gateway_id: str, payload: GatewayCreate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZAGateway).where(ZAGateway.id == gateway_id, ZAGateway.zone_id == zone_id))
    gateway = result.scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="gateway not found")
    data = payload.model_dump()
    data["zone_id"] = zone_id
    for field, value in data.items():
        setattr(gateway, field, value)
    await session.commit()
    await session.refresh(gateway)
    return gateway


@router.delete("/zones/{zone_id}/gateways/{gateway_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_gateway(zone_id: str, gateway_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZAGateway).where(ZAGateway.id == gateway_id, ZAGateway.zone_id == zone_id))
    gateway = result.scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="gateway not found")
    await session.delete(gateway)
    await session.commit()


@router.post("/zones/{zone_id}/gateways/{gateway_id}/test", dependencies=[Depends(require_admin)])
async def test_gateway(zone_id: str, gateway_id: str, session: AsyncSession = Depends(get_session)):
    """TCP-connect to the gateway's SSH port to verify reachability/health (stateless)."""
    result = await session.execute(select(ZAGateway).where(ZAGateway.id == gateway_id, ZAGateway.zone_id == zone_id))
    gateway = result.scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="gateway not found")

    reachable = False
    error_msg = ""
    start = time.monotonic()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(gateway.host, gateway.port or 22), timeout=5.0
        )
        writer.close()
        await writer.wait_closed()
        reachable = True
    except asyncio.TimeoutError:
        error_msg = "Connection timed out"
    except OSError as exc:
        error_msg = str(exc)
    latency_ms = int((time.monotonic() - start) * 1000)

    return {"gateway_id": gateway_id, "reachable": reachable, "latency_ms": latency_ms, "error": error_msg}
