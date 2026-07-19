"""SQLAlchemy ORM models — identity DB. Mirrors schema/{postgres,mysql}/schema.sql."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uid() -> str:
    return str(uuid.uuid4())


class ZARole(Base):
    __tablename__ = "za_roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["ZAUser"]] = relationship("ZAUser", back_populates="role", lazy="select")


class ZAUserGroup(Base):
    __tablename__ = "za_user_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    zabbix_usrgrpid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list["ZAUserGroupMember"]] = relationship("ZAUserGroupMember", back_populates="group", lazy="select")


class ZAUser(Base):
    __tablename__ = "za_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    zabbix_userid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("za_roles.id", ondelete="SET NULL"), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[str] = mapped_column(Text, default="")  # base32 seed, vault-encrypted (v1.1)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # v1.1
    # Which second factor is active, if any — "totp" (authenticator app, uses totp_secret/
    # totp_enabled above) or "email" (OTP mailed on demand, no persistent secret needed).
    # None means MFA is off. Kept separate from totp_enabled so email-OTP doesn't need to
    # repurpose TOTP-specific columns.
    mfa_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    role: Mapped[ZARole | None] = relationship("ZARole", back_populates="users")
    group_memberships: Mapped[list["ZAUserGroupMember"]] = relationship("ZAUserGroupMember", back_populates="user", lazy="select")


class ZAUserRole(Base):
    """Many-to-many user↔role assignment (v1.1 RBAC — a user can hold multiple roles)."""

    __tablename__ = "za_user_roles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("za_users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("za_roles.id", ondelete="CASCADE"), primary_key=True)


class ZAUserGroupMember(Base):
    __tablename__ = "za_user_group_members"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("za_users.id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("za_user_groups.id", ondelete="CASCADE"), primary_key=True)

    user: Mapped[ZAUser] = relationship("ZAUser", back_populates="group_memberships")
    group: Mapped[ZAUserGroup] = relationship("ZAUserGroup", back_populates="members")


class ZAGroupRole(Base):
    """Group→role grant (v2): membership in the group inherits these roles.
    Effective roles = direct za_user_roles ∪ roles from every group the user is in."""

    __tablename__ = "za_group_roles"

    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("za_user_groups.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("za_roles.id", ondelete="CASCADE"), primary_key=True)


class ZASession(Base):
    __tablename__ = "za_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("za_users.id", ondelete="CASCADE"), nullable=False)
    jwt_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ZAAuthorization(Base):
    """PAM rule: (user OR user_group) -> (host OR host_group, inventory DB) -> credential -> actions."""

    __tablename__ = "za_authorizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Legacy single-value columns — kept populated (first array element) for back-compat.
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("za_users.id", ondelete="CASCADE"), nullable=True)
    user_group_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("za_user_groups.id", ondelete="CASCADE"), nullable=True)
    host_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    host_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # v1.1 many-to-many: one rule may grant multiple users/groups access to multiple hosts/groups.
    user_ids: Mapped[list] = mapped_column(JSON, default=list)
    user_group_ids: Mapped[list] = mapped_column(JSON, default=list)
    host_ids: Mapped[list] = mapped_column(JSON, default=list)
    host_group_ids: Mapped[list] = mapped_column(JSON, default=list)
    credential_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    credential_ids: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    date_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_expired: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ZACommandGroup(Base):
    __tablename__ = "za_command_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    patterns: Mapped[list] = mapped_column(JSON, default=list)
    match_type: Mapped[str] = mapped_column(String(20), default="regex")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ZACommandFilter(Base):
    """SSH ACL: command group + scope -> allow|deny|confirm. Enforced by terminal-service (Phase 2)."""

    __tablename__ = "za_command_filters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    command_group_id: Mapped[str] = mapped_column(String(36), ForeignKey("za_command_groups.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("za_users.id", ondelete="CASCADE"), nullable=True)
    user_group_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("za_user_groups.id", ondelete="CASCADE"), nullable=True)
    host_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    host_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(20), default="deny")
    priority: Mapped[int] = mapped_column(Integer, default=50)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ZALoginAcl(Base):
    """Time/IP/host login restriction. Enforced by api-gateway + terminal-service (Phase 2)."""

    __tablename__ = "za_login_acls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("za_users.id", ondelete="CASCADE"), nullable=True)
    user_group_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("za_user_groups.id", ondelete="CASCADE"), nullable=True)
    ip_cidr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    time_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    time_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    days_of_week: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4, 5, 6])
    action: Mapped[str] = mapped_column(String(10), default="allow")
    priority: Mapped[int] = mapped_column(Integer, default=50)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ZAApiToken(Base):
    """Personal Access Token — Argon2id hash + API_TOKEN_PEPPER, raw token shown once."""

    __tablename__ = "za_api_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("za_users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, default=lambda: ["read"])
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ZAAuditLog(Base):
    __tablename__ = "za_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    username: Mapped[str] = mapped_column(String(100), default="")
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), default="")
    resource_id: Mapped[str] = mapped_column(String(36), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Tamper-evident hash chain (T9): seq is a strict monotonic order assigned under an
    # advisory lock; entry_hash = H(seq, prev_hash, payload). Nullable so the migration
    # doesn't need to backfill; every new row populates all three.
    seq: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ZALoginAttempt(Base):
    """DB-backed brute-force lockout state, keyed by "username|ip".

    Survives restarts (unlike a pure in-memory counter) and needs no redis in
    identity-service. ``fail_count`` accumulates within the attempt window;
    ``locked_until`` is set once the threshold is crossed.
    """

    __tablename__ = "za_login_attempts"

    key: Mapped[str] = mapped_column(String(320), primary_key=True)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ZAMailSettings(Base):
    """Singleton mail-delivery config for MFA email OTPs (mirrors ZALogBackendConfig's
    single-row pattern — services/inventory-service/app/models.py). Secrets
    (smtp_password, graph_client_secret) are vault-encrypted, never returned
    plaintext by the API (see api/mail_settings.py's masked-secret GET/PUT).
    """

    __tablename__ = "za_mail_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    provider: Mapped[str] = mapped_column(String(10), default="")  # "smtp" | "graph" | ""
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    from_address: Mapped[str] = mapped_column(String(320), default="")
    from_name: Mapped[str] = mapped_column(String(200), default="")

    smtp_host: Mapped[str] = mapped_column(String(255), default="")
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_username: Mapped[str] = mapped_column(String(320), default="")
    smtp_password: Mapped[str] = mapped_column(Text, default="")  # vault-encrypted
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True)

    graph_tenant_id: Mapped[str] = mapped_column(String(100), default="")
    graph_client_id: Mapped[str] = mapped_column(String(100), default="")
    graph_client_secret: Mapped[str] = mapped_column(Text, default="")  # vault-encrypted
    graph_sender_upn: Mapped[str] = mapped_column(String(320), default="")

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ZASetting(Base):
    """Generic key/value settings store (superadmin-editable via the UI).

    First key: "integration" -> {zabbix_console_url, zabbix_api_url, zabbix_api_token}.
    The gateway reads these DB-first and falls back to .env; the api token is never
    sent to the browser (see the /settings and /internal/settings endpoints).
    """

    __tablename__ = "za_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
