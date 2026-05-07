"""Endpoint /operator/workers — dashboard administrativo do operador (sem UI)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import AgentRunLog, AgentRunStatus, Role, User, WorkerHeartbeat
from app.queue.publisher import dead_letter_depth, queue_depth
from app.schemas.operator import (
    EngineDistribution,
    JobSnapshot,
    PendingLoginItem,
    WorkersDashboardResponse,
    WorkerSnapshot,
)

router = APIRouter(prefix="/operator", tags=["operator"])

# Sentinelas de login pendente (mesmo path do agent-runner broker).
_LOGIN_PENDING_DIR = Path.home() / ".jump-runner"


def _scan_pending_logins() -> list[PendingLoginItem]:
    items: list[PendingLoginItem] = []
    if not _LOGIN_PENDING_DIR.exists():
        return items
    for marker in _LOGIN_PENDING_DIR.glob("login-pending-*"):
        engine = marker.name.replace("login-pending-", "")
        try:
            session = marker.read_text(encoding="utf-8").strip()
        except OSError:
            session = "(unreadable)"
        items.append(PendingLoginItem(engine=engine, session=session))
    return items


@router.get("/workers", response_model=WorkersDashboardResponse)
async def workers_dashboard(
    request: Request,
    _user: User = Depends(require_any_role(Role.OPERATOR, Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> WorkersDashboardResponse:
    now = datetime.now(UTC)

    # Workers
    rows = (await db.execute(select(WorkerHeartbeat))).scalars().all()
    workers: list[WorkerSnapshot] = []
    for w in rows:
        last_seen = w.last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=UTC)
        workers.append(
            WorkerSnapshot(
                worker_id=w.worker_id,
                last_seen_at=last_seen,
                last_seen_ago_s=int((now - last_seen).total_seconds()),
                status=w.status,
                sessions_status=w.sessions_status,
                jobs_processed_today=w.jobs_processed_today,
                jobs_failed_today=w.jobs_failed_today,
            )
        )

    # Jobs em progresso (não-terminais)
    jobs_rows = (
        await db.execute(
            select(AgentRunLog).where(
                AgentRunLog.status.in_([AgentRunStatus.QUEUED, AgentRunStatus.RUNNING])
            )
        )
    ).scalars().all()
    jobs = [
        JobSnapshot(
            run_id=j.run_id,
            task_type=j.task_type.value,
            status=j.status.value,
            project_id=str(j.project_id) if j.project_id else None,
            proposal_id=str(j.proposal_id) if j.proposal_id else None,
            report_id=str(j.report_id) if j.report_id else None,
            created_at=j.created_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            engine_used=j.engine_used,
            route_used=j.route_used,
            failure_reason=j.failure_reason,
        )
        for j in jobs_rows
    ]

    # Distribuição de engines em jobs DONE hoje
    today = datetime(now.year, now.month, now.day, tzinfo=UTC)
    dist_rows = (
        await db.execute(
            select(AgentRunLog.engine_used, func.count())
            .where(
                AgentRunLog.status == AgentRunStatus.DONE,
                AgentRunLog.completed_at >= today,
            )
            .group_by(AgentRunLog.engine_used)
        )
    ).all()

    dist = EngineDistribution()
    for engine, count in dist_rows:
        if engine == "claude":
            dist.claude = count
        elif engine == "codex":
            dist.codex = count
        else:
            dist.none = count

    # Queue depth via Redis state
    redis = getattr(request.app.state, "redis", None)
    qd = await queue_depth(redis) if redis else 0
    dld = await dead_letter_depth(redis) if redis else 0

    return WorkersDashboardResponse(
        workers=workers,
        pending_logins=_scan_pending_logins(),
        queue_depth=qd,
        dead_letter_depth=dld,
        jobs_in_progress=jobs,
        expected_engine_distribution=dist,
    )
