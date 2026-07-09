"""Job run lifecycle: create DB record, dispatch executor, stream output to Redis."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Callable

import redis.asyncio as aioredis

from .config import get_settings
from .database import SessionLocal
from .models import ZAJobRun

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def execute(run_id: str, executor, request, settings=None) -> None:
    """Run a job: update DB status, stream output lines to Redis, finalize."""
    if settings is None:
        settings = get_settings()

    redis = get_redis()
    channel = f"job:{run_id}:log"
    max_lines = settings.max_output_lines

    async def publish_line(line: str) -> None:
        msg = json.dumps({"type": "line", "line": line})
        await redis.publish(channel, msg)
        async with SessionLocal() as session:
            run = await session.get(ZAJobRun, run_id)
            if run is not None:
                lines = list(run.output_lines or [])
                lines.append(line)
                run.output_lines = lines[-max_lines:]
                await session.commit()

    async with SessionLocal() as session:
        run = await session.get(ZAJobRun, run_id)
        if run is None:
            return
        run.status = "running"
        await session.commit()

    exit_code = None
    final_status = "error"
    try:
        result = await asyncio.wait_for(
            executor.execute(request, publish_line),
            timeout=settings.job_exec_timeout_seconds,
        )
        exit_code = result.exit_code if result.exit_code is not None else (0 if result.ok else 1)
        final_status = "success" if result.ok else "failed"
        if result.output:
            await publish_line(result.output)
    except asyncio.TimeoutError:
        final_status = "error"
        await publish_line(f"[error] job timed out after {settings.job_exec_timeout_seconds}s")
    except Exception as exc:
        final_status = "error"
        await publish_line(f"[error] {exc}")
        logger.exception("job run %s failed", run_id)

    async with SessionLocal() as session:
        run = await session.get(ZAJobRun, run_id)
        if run is not None:
            run.status = final_status
            run.exit_code = exit_code
            run.ended_at = datetime.now(timezone.utc)
            await session.commit()

    done_msg = json.dumps({"type": "done", "status": final_status, "exit_code": exit_code})
    await redis.publish(channel, done_msg)
