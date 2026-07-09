from __future__ import annotations

import jwt
import pydantic
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.pluginbase import discover_plugins, CredentialKind

from .. import audit
from ..config import get_settings
from ..database import get_session
from ..deps import require_admin, require_service_token
from ..models import ZACredential, ZACredentialHistory, ZACredentialHostLink, ZACredentialTemplate
from ..schemas import (
    CredentialCreate,
    CredentialOut,
    CredentialSecretOut,
    CredentialTemplateCreate,
    CredentialTemplateOut,
)
from ..vault import VaultDecryptError, decrypt, encrypt

router = APIRouter(tags=["credentials"], dependencies=[Depends(require_service_token)])

_credential_kinds: dict[str, CredentialKind] = discover_plugins("app.plugins.credentials", CredentialKind)


def _kind(secret_type: str) -> CredentialKind:
    kind = _credential_kinds.get(secret_type)
    if kind is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown secret_type '{secret_type}'")
    return kind


def _strength_score(secret_type: str, secret: dict) -> int | None:
    """zxcvbn score 0-4 for password credentials; None for keys/vault paths (Feature 9)."""
    if secret_type != "password":
        return None
    pwd = secret.get("password") or ""
    if not pwd:
        return None
    try:
        from zxcvbn import zxcvbn
        return int(zxcvbn(pwd)["score"])
    except Exception:
        return None


async def _credential_out(session: AsyncSession, cred: ZACredential) -> CredentialOut:
    result = await session.execute(select(ZACredentialHostLink.host_id).where(ZACredentialHostLink.credential_id == cred.id))
    host_ids = [h for (h,) in result.all()]
    return CredentialOut(
        id=cred.id,
        name=cred.name,
        template_id=cred.template_id,
        username=cred.username,
        secret_type=cred.secret_type,
        credential_scope=cred.credential_scope,
        is_default=cred.is_default,
        is_sudo=cred.is_sudo,
        is_push_account=cred.is_push_account,
        strength_score=cred.strength_score,
        last_rotated_at=cred.last_rotated_at,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
        host_ids=host_ids,
    )


# ── Credential Templates (Account Templates) ────────────────────────────────

@router.get("/credential-templates", response_model=list[CredentialTemplateOut])
async def list_credential_templates(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZACredentialTemplate))
    return result.scalars().all()


@router.post("/credential-templates", response_model=CredentialTemplateOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_credential_template(payload: CredentialTemplateCreate, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(ZACredentialTemplate).where(ZACredentialTemplate.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="template name already exists")
    template = ZACredentialTemplate(**payload.model_dump())
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


@router.put("/credential-templates/{template_id}", response_model=CredentialTemplateOut, dependencies=[Depends(require_admin)])
async def update_credential_template(template_id: str, payload: CredentialTemplateCreate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZACredentialTemplate).where(ZACredentialTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")
    for field, value in payload.model_dump().items():
        setattr(template, field, value)
    await session.commit()
    await session.refresh(template)
    return template


@router.delete("/credential-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_credential_template(template_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ZACredentialTemplate).where(ZACredentialTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")
    await session.delete(template)
    await session.commit()


# ── Credentials ───────────────────────────────────────────────────────────────

@router.get("/credentials", response_model=list[CredentialOut])
async def list_credentials(host_id: str | None = None, session: AsyncSession = Depends(get_session)):
    if host_id:
        stmt = (
            select(ZACredential)
            .join(ZACredentialHostLink, ZACredential.id == ZACredentialHostLink.credential_id)
            .where(ZACredentialHostLink.host_id == host_id)
        )
    else:
        stmt = select(ZACredential)
    result = await session.execute(stmt)
    return [await _credential_out(session, c) for c in result.scalars().all()]


@router.post("/credentials", response_model=CredentialOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_credential(
    payload: CredentialCreate,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    kind = _kind(payload.secret_type)
    try:
        kind.validate(payload.secret)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ciphertext = encrypt(kind.encode(payload.secret))

    cred = ZACredential(
        name=payload.name,
        template_id=payload.template_id,
        username=payload.username,
        secret_type=payload.secret_type,
        secret_ciphertext=ciphertext,
        credential_scope=payload.credential_scope,
        is_default=payload.is_default,
        is_sudo=payload.is_sudo,
        is_push_account=payload.is_push_account,
        strength_score=_strength_score(payload.secret_type, payload.secret),
    )
    session.add(cred)
    await session.flush()

    for host_id in payload.host_ids:
        session.add(ZACredentialHostLink(credential_id=cred.id, host_id=host_id))

    await session.commit()
    await session.refresh(cred)

    await audit.log_action(
        user_id=actor_id, username=actor_name or "", action="credential.create",
        resource_type="credential", resource_id=cred.id,
        details={"name": cred.name, "secret_type": cred.secret_type, "username": cred.username},
    )
    return await _credential_out(session, cred)


@router.put("/credentials/{credential_id}", response_model=CredentialOut, dependencies=[Depends(require_admin)])
async def update_credential(
    credential_id: str,
    payload: CredentialCreate,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    result = await session.execute(select(ZACredential).where(ZACredential.id == credential_id))
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credential not found")

    cred.name = payload.name
    cred.template_id = payload.template_id
    cred.username = payload.username
    cred.secret_type = payload.secret_type
    cred.credential_scope = payload.credential_scope
    cred.is_default = payload.is_default
    cred.is_sudo = payload.is_sudo
    cred.is_push_account = payload.is_push_account

    if payload.secret:  # empty dict = keep existing ciphertext
        kind = _kind(payload.secret_type)
        try:
            kind.validate(payload.secret)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        cred.secret_ciphertext = encrypt(kind.encode(payload.secret))
        cred.strength_score = _strength_score(payload.secret_type, payload.secret)

    existing = await session.execute(select(ZACredentialHostLink).where(ZACredentialHostLink.credential_id == credential_id))
    for link in existing.scalars().all():
        await session.delete(link)
    for host_id in payload.host_ids:
        session.add(ZACredentialHostLink(credential_id=credential_id, host_id=host_id))

    await session.commit()
    await session.refresh(cred)

    await audit.log_action(
        user_id=actor_id, username=actor_name or "", action="credential.update",
        resource_type="credential", resource_id=cred.id,
    )
    return await _credential_out(session, cred)


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_credential(
    credential_id: str,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    result = await session.execute(select(ZACredential).where(ZACredential.id == credential_id))
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credential not found")

    await session.delete(cred)
    await session.commit()

    await audit.log_action(
        user_id=actor_id, username=actor_name or "", action="credential.delete",
        resource_type="credential", resource_id=credential_id,
    )


@router.get("/credentials/weak", response_model=list[CredentialOut], dependencies=[Depends(require_admin)])
async def list_weak_credentials(session: AsyncSession = Depends(get_session)):
    """Password credentials whose zxcvbn score is below the configured threshold (Feature 9)."""
    threshold = get_settings().weak_credential_threshold
    result = await session.execute(
        select(ZACredential).where(
            ZACredential.strength_score.isnot(None),
            ZACredential.strength_score < threshold,
        )
    )
    return [await _credential_out(session, c) for c in result.scalars().all()]


@router.get("/credentials/{credential_id}/reveal", response_model=CredentialSecretOut, dependencies=[Depends(require_admin)])
async def reveal_credential(
    credential_id: str,
    session: AsyncSession = Depends(get_session),
    reveal_token: str = Header("", alias="X-Reveal-Token"),
    actor_id: str | None = Header(default=None, alias="X-User-Id"),
    actor_name: str | None = Header(default=None, alias="X-User-Name"),
):
    """MFA-gated secret reveal (Feature 6). Requires a short-lived reveal token minted by
    identity-service /auth/mfa/verify. The token is bound to BOTH the specific credential
    (``cid``) and the user (``sub``) it was minted for, so it cannot be replayed to reveal a
    different credential or by a different user."""
    settings = get_settings()
    if not reveal_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="reveal token required")
    try:
        claims = jwt.decode(reveal_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired reveal token") from exc
    if claims.get("purpose") != "credential_reveal":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wrong token purpose")
    # Token must be scoped to THIS credential and THIS caller.
    if claims.get("cid") != credential_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="reveal token not valid for this credential")
    if actor_id and claims.get("sub") and claims["sub"] != actor_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="reveal token issued for a different user")

    result = await session.execute(select(ZACredential).where(ZACredential.id == credential_id))
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credential not found")

    kind = _kind(cred.secret_type)
    try:
        secret = kind.decode(decrypt(cred.secret_ciphertext))
    except VaultDecryptError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    await audit.log_action(
        user_id=actor_id, username=actor_name or "", action="credential.viewed",
        resource_type="credential", resource_id=cred.id,
        details={"event_type": "credential_viewed", "name": cred.name},
    )
    return CredentialSecretOut(id=cred.id, username=cred.username, secret_type=cred.secret_type, secret=secret)


@router.get("/internal/credentials/{credential_id}/secret", response_model=CredentialSecretOut)
async def get_credential_secret(credential_id: str, session: AsyncSession = Depends(get_session)):
    """Decrypted secret — internal only, consumed by terminal-service/automation-service (Phase 2/3)."""
    result = await session.execute(select(ZACredential).where(ZACredential.id == credential_id))
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credential not found")

    kind = _kind(cred.secret_type)
    try:
        secret = kind.decode(decrypt(cred.secret_ciphertext))
    except VaultDecryptError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return CredentialSecretOut(
        id=cred.id, username=cred.username, secret_type=cred.secret_type, secret=secret,
        is_sudo=cred.is_sudo, is_push_account=cred.is_push_account,
    )


class _SecretUpdatePayload(pydantic.BaseModel):
    secret: dict


@router.put("/internal/credentials/{credential_id}/secret", status_code=status.HTTP_204_NO_CONTENT)
async def update_credential_secret(
    credential_id: str,
    payload: _SecretUpdatePayload,
    session: AsyncSession = Depends(get_session),
    actor_id: str = Header("", alias="X-User-Id"),
):
    """Re-encrypt and overwrite a credential secret — called exclusively by rotate_secret executor after all hosts updated."""
    result = await session.execute(select(ZACredential).where(ZACredential.id == credential_id))
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credential not found")

    kind = _kind(cred.secret_type)
    kind.validate(payload.secret)

    # Archive the prior ciphertext before overwriting (Feature 10 history).
    if cred.secret_ciphertext:
        session.add(ZACredentialHistory(
            credential_id=cred.id,
            secret_ciphertext=cred.secret_ciphertext,
            rotated_by=actor_id or None,
        ))

    cred.secret_ciphertext = encrypt(kind.encode(payload.secret))
    cred.strength_score = _strength_score(cred.secret_type, payload.secret)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    cred.updated_at = now
    cred.last_rotated_at = now
    await session.commit()

    await audit.log_action(
        user_id=actor_id or "system", username="", action="credential.secret_rotated",
        resource_type="credential", resource_id=credential_id,
        details={"event_type": "credential_rotated", "note": "secret rotated"},
    )
