"""Schemas Pydantic para o dashboard administrativo do operador."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WorkerSnapshot(BaseModel):
    worker_id: str
    last_seen_at: datetime
    last_seen_ago_s: int
    status: str
    sessions_status: dict
    jobs_processed_today: int
    jobs_failed_today: int


class PendingLoginItem(BaseModel):
    engine: str  # claude | codex
    session: str  # nome da sessão tmux


class JobSnapshot(BaseModel):
    run_id: str
    task_type: str
    status: str
    project_id: str | None
    proposal_id: str | None
    report_id: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    engine_used: str | None
    route_used: str | None
    failure_reason: str | None


class EngineDistribution(BaseModel):
    """Quantos jobs concluídos hoje rodaram em cada engine.

    Esqueleto para o PMO acompanhar saúde da política de fallback.
    Mesmo zerado é informativo — sinaliza que ainda não houve atividade.
    """

    claude: int = 0
    codex: int = 0
    none: int = 0  # jobs failed sem nenhum engine ter sido usado


class WorkersDashboardResponse(BaseModel):
    workers: list[WorkerSnapshot]
    pending_logins: list[PendingLoginItem]
    queue_depth: int
    dead_letter_depth: int
    jobs_in_progress: list[JobSnapshot]
    expected_engine_distribution: EngineDistribution
