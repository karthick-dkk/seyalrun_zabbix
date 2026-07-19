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

from .models import ZAUserGroup, ZAUserGroupMember


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
