"""Server-side session store (Redis-backed). Replaces the old self-contained
JWT: the browser holds only an opaque, unguessable id — every claim (roles,
kiosk binding, must-change-password) lives here, looked up per request by
api-gateway (see api-gateway/app/security.py::lookup_session), never decoded
client-side. Revocation is `DEL session:<id>` — first-class, not a bolt-on.
"""

from __future__ import annotations

import json
import secrets
import time

import redis.asyncio as redis

SESSION_PREFIX = "session:"


def _key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}"


async def create_session(
    client: redis.Redis,
    *,
    user_id: str,
    username: str,
    role: str,
    roles: list[str],
    idle_minutes: int,
    kiosk_host_id: str | None = None,
    pwc: bool = False,
    mfa_pending: bool = False,
) -> str:
    """Mint a new session, seeded with a fresh created_at/last_seen_at. Initial
    TTL is the idle window — api-gateway slides it forward on every request,
    capped at session_absolute_hours from created_at (see lookup_session)."""
    session_id = secrets.token_urlsafe(32)
    now = int(time.time())
    blob = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "roles": roles,
        "kiosk": bool(kiosk_host_id),
        "kiosk_host_id": kiosk_host_id,
        "pwc": pwc,
        "mfa_pending": mfa_pending,
        "created_at": now,
        "last_seen_at": now,
    }
    await client.set(_key(session_id), json.dumps(blob), ex=idle_minutes * 60)
    return session_id
