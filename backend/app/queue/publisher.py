"""Publisher de jobs na fila Redis `jobs.agent`.

Spec v3 §7.4 — schema do job:
{
  "run_id": "ext-prop-2026-05-07-001",  # idempotente, PK do AgentRunLog
  "task_type": "proposal_extraction" | "report_analysis" | "portfolio_pattern",
  "engine_preference": "claude" | "codex" | null,
  "context": { project_id, proposal_id, report_id, ... },
  "input_files": [ { "key": "proposals/.../v1.pdf", "kind": "proposal" } ],
  "output_path_hint": "...",                  # nome do output esperado
  "schema_hint": { ... },                     # JSON schema esperado
  "timeout_hard_s": 600,
  "heartbeat_s": 30,
  "enqueued_at": "ISO8601"
}

Idempotência:
  - se já existe AgentRunLog com run_id, NÃO publica de novo (retorna
    existing). Garantia de "job só roda uma vez" mesmo com retry HTTP.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis_async
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import AgentRunLog, AgentRunStatus, TaskType

QUEUE_KEY = "jobs.agent"
DEAD_LETTER_KEY = "jobs.agent.dead"


log = get_logger("queue.publisher")


def make_run_id(*, task_type: TaskType, project_id: uuid.UUID | None = None) -> str:
    """Gera um run_id determinístico-aparente para humanos. Não é estritamente único."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    suffix = uuid.uuid4().hex[:8]
    pid = str(project_id)[:8] if project_id else "global"
    short_type = {
        TaskType.PROPOSAL_EXTRACTION: "ext-prop",
        TaskType.REPORT_ANALYSIS: "rep-ana",
        TaskType.PORTFOLIO_PATTERN: "port-pat",
    }[task_type]
    return f"{short_type}-{today}-{pid}-{suffix}"


def _build_payload(
    *,
    run_id: str,
    task_type: TaskType,
    context: dict[str, Any],
    input_files: list[dict[str, str]],
    output_path_hint: str,
    schema_hint: dict[str, Any] | None,
    timeout_hard_s: int,
    heartbeat_s: int,
    engine_preference: str | None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task_type": task_type.value,
        "engine_preference": engine_preference,
        "context": context,
        "input_files": input_files,
        "output_path_hint": output_path_hint,
        "schema_hint": schema_hint,
        "timeout_hard_s": timeout_hard_s,
        "heartbeat_s": heartbeat_s,
        "enqueued_at": datetime.now(UTC).isoformat(),
    }


async def enqueue_agent_job(
    *,
    db: AsyncSession,
    redis: redis_async.Redis,
    task_type: TaskType,
    project_id: uuid.UUID | None = None,
    proposal_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    context: dict[str, Any] | None = None,
    input_files: list[dict[str, str]] | None = None,
    output_path_hint: str = "out.json",
    schema_hint: dict[str, Any] | None = None,
    timeout_hard_s: int = 600,
    heartbeat_s: int = 30,
    engine_preference: str | None = None,
    run_id: str | None = None,
) -> AgentRunLog:
    """Cria AgentRunLog e publica o job no Redis. Idempotente por run_id.

    Se um log com o run_id já existe e está em estado terminal (done|failed|expired),
    devolve o existente sem republish. Se está em queued|running, idem (worker
    já está processando).
    """
    run_id = run_id or make_run_id(task_type=task_type, project_id=project_id)

    # Idempotência: verifica se já existe
    existing = (
        await db.execute(select(AgentRunLog).where(AgentRunLog.run_id == run_id))
    ).scalar_one_or_none()
    if existing:
        log.info("queue.enqueue.dedup", run_id=run_id, status=existing.status.value)
        return existing

    full_context = {**(context or {})}
    if project_id:
        full_context.setdefault("project_id", str(project_id))
    if proposal_id:
        full_context.setdefault("proposal_id", str(proposal_id))
    if report_id:
        full_context.setdefault("report_id", str(report_id))

    payload = _build_payload(
        run_id=run_id,
        task_type=task_type,
        context=full_context,
        input_files=input_files or [],
        output_path_hint=output_path_hint,
        schema_hint=schema_hint,
        timeout_hard_s=timeout_hard_s,
        heartbeat_s=heartbeat_s,
        engine_preference=engine_preference,
    )

    new_log = AgentRunLog(
        run_id=run_id,
        task_type=task_type,
        project_id=project_id,
        proposal_id=proposal_id,
        report_id=report_id,
        status=AgentRunStatus.QUEUED,
        attempts=[],
    )
    db.add(new_log)
    # flush antes do publish para garantir que o registro existe se o worker
    # imediatamente puxar o job
    await db.flush()

    await redis.rpush(QUEUE_KEY, json.dumps(payload))
    log.info(
        "queue.enqueue.published",
        run_id=run_id,
        task_type=task_type.value,
        project_id=str(project_id) if project_id else None,
    )

    await db.commit()
    await db.refresh(new_log)
    return new_log


async def queue_depth(redis: redis_async.Redis) -> int:
    """Tamanho da fila (jobs queued)."""
    n = await redis.llen(QUEUE_KEY)
    return int(n or 0)


async def dead_letter_depth(redis: redis_async.Redis) -> int:
    n = await redis.llen(DEAD_LETTER_KEY)
    return int(n or 0)


__all__ = [
    "DEAD_LETTER_KEY",
    "QUEUE_KEY",
    "dead_letter_depth",
    "enqueue_agent_job",
    "make_run_id",
    "queue_depth",
]
