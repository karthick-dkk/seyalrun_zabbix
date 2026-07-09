from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON

from libs.dbcore import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class ZAProject(Base):
    __tablename__ = "za_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    git_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    git_branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class ZAJobTemplate(Base):
    __tablename__ = "za_job_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    playbook_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    script_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="hosts")
    target_host_ids: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    target_host_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    credential_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject_credential_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    survey_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    default_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Caller-supplied param keys this template accepts (allowlist). Empty list means
    # callers may supply no extra params beyond what survey_schema/default_params declare.
    # script_content / playbook_path are NEVER caller-supplied — they come from the
    # template only (see app/_params.py), which is what closes the webhook→executor
    # command-injection path.
    allowed_param_keys: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    quick_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class ZASchedule(Base):
    __tablename__ = "za_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_template_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    params_override: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ZAJobRun(Base):
    __tablename__ = "za_job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_template_id: Mapped[str] = mapped_column(String(36), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_lines: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    host_results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ZASecretManagementJob(Base):
    __tablename__ = "za_secret_management_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_credential_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_host_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schedule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ZAHousekeepingJob(Base):
    """Scheduled maintenance task with admin-tunable cron + manual trigger (v1.1 Feature 3)."""

    __tablename__ = "za_housekeeping_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    cron_override: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    last_run_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_trigger: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
