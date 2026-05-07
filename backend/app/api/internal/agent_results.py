"""Callback `/internal/agent-results/{run_id}` chamado pelo worker remoto.

Spec: v3 §7.5. Idempotência:
- estados terminais (done, failed, expired): não sobrescreve. Devolve duplicated=True.
- estados não-terminais (queued, running): aceita e atualiza.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.core.worker_auth import require_worker_auth
from app.models import AgentRunLog, AgentRunStatus
from app.schemas.worker import AgentResultAck, AgentResultPayload

router = APIRouter(prefix="/internal", tags=["internal"])

log = get_logger("internal.agent_results")

_TERMINAL = {AgentRunStatus.DONE, AgentRunStatus.FAILED, AgentRunStatus.EXPIRED}


@router.post(
    "/agent-results/{run_id}",
    response_model=AgentResultAck,
)
async def report_agent_result(
    run_id: str,
    request: Request,
    body: bytes = Depends(require_worker_auth),
    db: AsyncSession = Depends(get_db),
) -> AgentResultAck:
    # body já validado por HMAC. Parse manual (não passou pelo Pydantic
    # automático — Pydantic ler via Depends seria duplicar leitura do body).
    try:
        payload = AgentResultPayload.model_validate(json.loads(body or b"{}"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"payload inválido: {exc}") from exc

    existing = (
        await db.execute(select(AgentRunLog).where(AgentRunLog.run_id == run_id))
    ).scalar_one_or_none()
    if not existing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"AgentRunLog {run_id!r} não existe"
        )

    if existing.status in _TERMINAL:
        # Replay com payload diferente — idempotente, NÃO sobrescreve
        log.info(
            "agent_results.replay_ignored",
            run_id=run_id,
            existing_status=existing.status.value,
            payload_success=payload.success,
        )
        return AgentResultAck(
            accepted=False,
            run_id=run_id,
            status=existing.status,
            duplicated=True,
            note="estado terminal já consolidado; replay ignorado",
        )

    new_status = AgentRunStatus.DONE if payload.success else AgentRunStatus.FAILED

    existing.status = new_status
    existing.engine_used = payload.engine_used
    existing.route_used = payload.route_used
    existing.failover_occurred = bool(
        len({a.get("engine") for a in payload.attempts}) > 1
    )
    existing.attempts = payload.attempts
    existing.duration_s = payload.duration_s
    existing.worker_id = payload.worker_id
    existing.artifact_path = payload.artifact_path
    existing.failure_reason = payload.failure_reason
    existing.failure_detail = payload.failure_detail
    existing.completed_at = datetime.now(UTC)

    await db.commit()
    log.info(
        "agent_results.accepted",
        run_id=run_id,
        status=new_status.value,
        engine=payload.engine_used,
        route=payload.route_used,
        duration_s=payload.duration_s,
    )
    return AgentResultAck(
        accepted=True,
        run_id=run_id,
        status=new_status,
        duplicated=False,
    )
