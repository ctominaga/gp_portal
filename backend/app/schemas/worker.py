"""Schemas Pydantic para callbacks do worker."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models import AgentRunStatus


class WorkerHeartbeatPayload(BaseModel):
    worker_id: str
    status: str = "ok"
    sessions_status: dict[str, Any] = Field(default_factory=dict)
    jobs_processed_today: int = 0
    jobs_failed_today: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResultPayload(BaseModel):
    """Resultado final reportado pelo worker para o backend."""

    success: bool
    engine_used: str | None = None
    route_used: str | None = None
    artifact_data: dict[str, Any] | None = None
    artifact_path: str | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    duration_s: float | None = None
    failure_reason: str | None = None
    failure_detail: str | None = None
    worker_id: str | None = None


class AgentResultAck(BaseModel):
    accepted: bool
    run_id: str
    status: AgentRunStatus
    duplicated: bool = False
    note: str | None = None
