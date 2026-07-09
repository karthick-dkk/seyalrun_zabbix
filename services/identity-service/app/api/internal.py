"""Internal endpoints — called by api-gateway / future terminal-service, never exposed to the host."""

from __future__ import annotations

import ipaddress
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import log_action
from ..database import get_session
from ..deps import require_service_token
from ..models import (
    ZAApiToken,
    ZAAuthorization,
    ZACommandFilter,
    ZACommandGroup,
    ZALoginAcl,
    ZARole,
    ZAUser,
    ZAUserGroupMember,
    ZAUserRole,
)
from ..schemas import TokenVerifyRequest, TokenVerifyResponse
from ..security import verify_pat

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_service_token)])


# ── Many-to-many authorization helpers (v1.1) ────────────────────────────────

async def _user_is_admin(session: AsyncSession, user: ZAUser) -> bool:
    """Effective-role authz-bypass check (group-aware). Only superadmin/admin bypass
    the mandatory za_authorization resource gate; every other role is default-deny."""
    from ..rbacresolve import effective_roles
    from libs.rbaccore import bypasses_authz
    return bypasses_authz(await effective_roles(session, user.id))


def _authz_matches_principal(authz: ZAAuthorization, user_id: str, group_ids: set[str]) -> bool:
    users = set(authz.user_ids or [])
    if authz.user_id:
        users.add(authz.user_id)
    if user_id in users:
        return True
    ugroups = set(authz.user_group_ids or [])
    if authz.user_group_id:
        ugroups.add(authz.user_group_id)
    return bool(ugroups & group_ids)


def _authz_hosts(authz: ZAAuthorization) -> set[str]:
    hs = set(authz.host_ids or [])
    if authz.host_id:
        hs.add(authz.host_id)
    return hs


def _authz_host_groups(authz: ZAAuthorization) -> set[str]:
    hg = set(authz.host_group_ids or [])
    if authz.host_group_id:
        hg.add(authz.host_group_id)
    return hg


class AuditEntry(BaseModel):
    user_id: str | None = None
    username: str = ""
    action: str
    resource_type: str = ""
    resource_id: str = ""
    details: dict = {}
    ip_address: str = ""


@router.post("/audit")
async def write_audit(entry: AuditEntry, session: AsyncSession = Depends(get_session)):
    """Allows other services (e.g. inventory-service) to append to the shared audit log."""
    await log_action(
        session,
        user_id=entry.user_id,
        username=entry.username,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        details=entry.details,
        ip_address=entry.ip_address,
    )
    return {"ok": True}


@router.get("/authz/host-ids")
async def authz_host_ids(
    user_id: str = Query(...),
    strict: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    """strict=True skips the superadmin/admin bypass and always resolves real
    za_authorizations records — used by terminal-service so SSH session creation
    can never rely on role alone. Other callers (api-gateway nav gating,
    recording-service visibility) keep the existing bypass by omitting it."""
    user_result = await session.execute(select(ZAUser).where(ZAUser.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return {"host_ids": [], "host_group_ids": [], "is_admin": False}

    if not strict and await _user_is_admin(session, user):
        return {"host_ids": [], "host_group_ids": [], "is_admin": True}

    group_result = await session.execute(select(ZAUserGroupMember.group_id).where(ZAUserGroupMember.user_id == user_id))
    group_ids = {g for (g,) in group_result.all()}

    now = datetime.now(timezone.utc)
    authz_result = await session.execute(select(ZAAuthorization).where(ZAAuthorization.enabled.is_(True)))

    host_ids: set[str] = set()
    host_group_ids: set[str] = set()
    for authz in authz_result.scalars().all():
        if authz.date_start and authz.date_start > now:
            continue
        if authz.date_expired and authz.date_expired < now:
            continue
        if not _authz_matches_principal(authz, user_id, group_ids):
            continue
        host_ids.update(_authz_hosts(authz))
        host_group_ids.update(_authz_host_groups(authz))

    return {"host_ids": list(host_ids), "host_group_ids": list(host_group_ids), "is_admin": False}


@router.get("/command-filters")
async def internal_command_filters(
    user_id: str = Query(...),
    host_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Resolve applicable command filters for a user (+ optional host) — consumed by terminal-service.

    Returns {filters: [...], default_deny: bool}.  A filter with action="default_deny" acts as a
    global block-all policy marker for that user/host scope: it sets default_deny=True and is
    excluded from the filters list (it has no pattern to match against).
    """
    group_result = await session.execute(select(ZAUserGroupMember.group_id).where(ZAUserGroupMember.user_id == user_id))
    group_ids = [g for (g,) in group_result.all()]

    # A filter with NO user_id/user_group_id set ("Principal: Any" in the UI) is meant
    # to apply to every caller — but SQL's `=` never matches a NULL column, so without
    # this explicit branch such filters were silently never returned to ANYONE (a false
    # sense of security: shown as "Enabled" in the admin UI, enforced for no one).
    conditions = (
        (ZACommandFilter.user_id == user_id)
        | (ZACommandFilter.user_group_id.in_(group_ids or [""]))
        | (ZACommandFilter.user_id.is_(None) & ZACommandFilter.user_group_id.is_(None))
    )
    result = await session.execute(
        select(ZACommandFilter).where(ZACommandFilter.enabled.is_(True), conditions).order_by(ZACommandFilter.priority.desc())
    )
    filters = result.scalars().all()
    if host_id:
        filters = [f for f in filters if f.host_id in (None, host_id)]

    out = []
    default_deny = False
    for f in filters:
        if f.action == "default_deny":
            default_deny = True
            continue  # policy marker — no pattern to evaluate, just sets the fallback mode
        group_result2 = await session.execute(select(ZACommandGroup).where(ZACommandGroup.id == f.command_group_id))
        group = group_result2.scalar_one_or_none()
        out.append(
            {
                "id": f.id,
                "name": f.name,
                "action": f.action,
                "priority": f.priority,
                "patterns": group.patterns if group else [],
                "match_type": group.match_type if group else "regex",
            }
        )
    return {"filters": out, "default_deny": default_deny}


@router.get("/login-acls/check")
async def login_acls_check(
    user_id: str = Query(...),
    ip: str = Query(default=""),
    now_iso: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
):
    """Evaluate za_login_acls for user_id. Returns {allowed, matched_rule}.
    First matching enabled rule wins (by priority desc); no match → allowed=True."""
    group_result = await session.execute(
        select(ZAUserGroupMember.group_id).where(ZAUserGroupMember.user_id == user_id)
    )
    group_ids = [g for (g,) in group_result.all()]

    # Same NULL-comparison gap as command filters above: a rule with no
    # user_id/user_group_id ("Principal: Any") must still match every caller.
    conditions = (
        (ZALoginAcl.user_id == user_id)
        | (ZALoginAcl.user_group_id.in_(group_ids or [""]))
        | (ZALoginAcl.user_id.is_(None) & ZALoginAcl.user_group_id.is_(None))
    )
    result = await session.execute(
        select(ZALoginAcl)
        .where(ZALoginAcl.enabled.is_(True), conditions)
        .order_by(ZALoginAcl.priority.desc())
    )
    acls = result.scalars().all()

    try:
        now_dt = datetime.fromisoformat(now_iso) if now_iso else datetime.now(timezone.utc)
    except ValueError:
        now_dt = datetime.now(timezone.utc)

    now_time = now_dt.strftime("%H:%M")
    now_dow = now_dt.weekday()  # 0=Monday, 6=Sunday

    for acl in acls:
        if acl.ip_cidr and ip:
            try:
                if ipaddress.ip_address(ip) not in ipaddress.ip_network(acl.ip_cidr, strict=False):
                    continue
            except ValueError:
                continue

        if acl.time_start and acl.time_end:
            if not (acl.time_start <= now_time <= acl.time_end):
                continue

        if acl.days_of_week is not None and len(acl.days_of_week) < 7:
            if now_dow not in acl.days_of_week:
                continue

        return {"allowed": acl.action == "allow", "matched_rule": acl.name}

    return {"allowed": True, "matched_rule": None}


@router.get("/authz/resolve")
async def authz_resolve(
    user_id: str = Query(...),
    host_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Return {credential_id, actions} from the best-matching za_authorizations row
    for (user_id, host_id). Used by terminal-service to default credential and
    verify 'ssh' is in the allowed actions. Returns nulls if no match."""
    group_result = await session.execute(
        select(ZAUserGroupMember.group_id).where(ZAUserGroupMember.user_id == user_id)
    )
    group_ids = {g for (g,) in group_result.all()}

    now = datetime.now(timezone.utc)
    result = await session.execute(select(ZAAuthorization).where(ZAAuthorization.enabled.is_(True)))

    best: ZAAuthorization | None = None
    for authz in result.scalars().all():
        if authz.date_start and authz.date_start > now:
            continue
        if authz.date_expired and authz.date_expired < now:
            continue
        if not _authz_matches_principal(authz, user_id, group_ids):
            continue
        # Direct host match takes priority over a host-group-only match.
        if host_id in _authz_hosts(authz):
            best = authz
            break
        if _authz_host_groups(authz) and best is None:
            best = authz

    if best is None:
        return {"credential_id": None, "credential_ids": [], "actions": []}
    cred_ids = list(best.credential_ids or ([best.credential_id] if best.credential_id else []))
    return {"credential_id": cred_ids[0] if cred_ids else None, "credential_ids": cred_ids, "actions": best.actions or []}


@router.post("/tokens/verify", response_model=TokenVerifyResponse)
async def verify_token(payload: TokenVerifyRequest, session: AsyncSession = Depends(get_session)):
    if not payload.token.startswith("sr_"):
        return TokenVerifyResponse(valid=False)

    candidates = await session.execute(
        select(ZAApiToken).where(ZAApiToken.token_prefix == payload.token[:9], ZAApiToken.revoked_at.is_(None))
    )
    now = datetime.now(timezone.utc)
    for token in candidates.scalars().all():
        if token.expires_at and token.expires_at < now:
            continue
        if not verify_pat(payload.token, token.token_hash):
            continue

        token.last_used_at = now
        await session.commit()

        user_result = await session.execute(select(ZAUser).where(ZAUser.id == token.user_id))
        user = user_result.scalar_one_or_none()
        if user is None or not user.is_active:
            return TokenVerifyResponse(valid=False)

        # PAT role = effective primary role (group-aware), not the legacy role_id.
        from ..rbacresolve import effective_roles
        from libs.rbaccore import primary_role
        eff = await effective_roles(session, user.id)
        role_name = primary_role(eff) if eff else "user"

        return TokenVerifyResponse(
            valid=True, user_id=user.id, username=user.username, role=role_name, scopes=token.scopes,
        )

    return TokenVerifyResponse(valid=False)


@router.get("/users/{user_id}/roles")
async def internal_user_roles(user_id: str, session: AsyncSession = Depends(get_session)):
    """The user's CURRENT effective role names (direct ∪ group-granted). The api-gateway
    calls this so role/group changes apply without a re-login. "known" lets the gateway
    tell an empty-but-valid user (=[] → deny) from an unreachable identity-service
    (→ stale-JWT fallback) — the removed-from-group access-drop depends on it."""
    from ..rbacresolve import effective_roles
    user = await session.get(ZAUser, user_id)
    if user is None:
        return {"roles": [], "known": False}
    return {"roles": await effective_roles(session, user_id), "known": True}


@router.get("/settings/integration")
async def internal_get_integration(session: AsyncSession = Depends(get_session)):
    """Full Zabbix integration settings INCLUDING the api token — for the gateway
    to consume server-side (never returned to the browser). Service-token gated."""
    from ..models import ZASetting

    row = await session.get(ZASetting, "integration")
    v = dict(row.value) if row and isinstance(row.value, dict) else {}
    return {
        "zabbix_console_url": v.get("zabbix_console_url", ""),
        "zabbix_api_url": v.get("zabbix_api_url", ""),
        "zabbix_api_token": v.get("zabbix_api_token", ""),
    }
