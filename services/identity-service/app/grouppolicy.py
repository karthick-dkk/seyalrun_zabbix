"""Effective group POLICY resolver (v1.2) — the ONE place a user's group
memberships are reduced into policy decisions, mirroring rbacresolve.py's
role-resolution shape but for direct group settings rather than role grants.

Policies are OR-reduced across every group a user belongs to: if ANY group
requires MFA, the user is required to enroll; there's no "most specific
group wins" precedence — enforcement is a floor, not an override.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ZAGroupNotifyConfig, ZAUserGroup, ZAUserGroupMember

_SEVERITY_RANK = {"info": 0, "medium": 1, "critical": 2}


async def effective_group_policies(session: AsyncSession, user_id: str) -> dict:
    docs = [
        doc for (doc,) in (
            await session.execute(
                select(ZAUserGroup.policies)
                .join(ZAUserGroupMember, ZAUserGroupMember.group_id == ZAUserGroup.id)
                .where(ZAUserGroupMember.user_id == user_id)
            )
        ).all()
    ]
    return {
        "mfa_enforced": any((d or {}).get("mfa_enforced") for d in docs),
        "setup_wizard": any((d or {}).get("setup_wizard") for d in docs),
    }


async def notify_recipients(session: AsyncSession, user_id: str, severity: str) -> list[str]:
    """Every recipient email that should hear about a notification of this
    severity, across every group the user belongs to with notifications
    enabled and a min_severity at or below it. Deduped, order-independent."""
    rows = (
        await session.execute(
            select(ZAUserGroup.id, ZAUserGroup.policies)
            .join(ZAUserGroupMember, ZAUserGroupMember.group_id == ZAUserGroup.id)
            .where(ZAUserGroupMember.user_id == user_id)
        )
    ).all()
    eligible_group_ids = [gid for gid, policies in rows if (policies or {}).get("notifications_enabled")]
    if not eligible_group_ids:
        return []

    cfgs = (
        await session.execute(select(ZAGroupNotifyConfig).where(ZAGroupNotifyConfig.group_id.in_(eligible_group_ids)))
    ).scalars().all()
    sev_rank = _SEVERITY_RANK.get(severity, 0)
    emails: set[str] = set()
    for cfg in cfgs:
        if sev_rank >= _SEVERITY_RANK.get(cfg.min_severity, 1):
            emails.update(cfg.emails or [])
    return sorted(emails)
