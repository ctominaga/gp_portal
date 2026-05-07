"""Schemas Pydantic para o fluxo de aprovação de Report (3 estágios)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import ApprovalDecision, ApprovalStage


class ApprovalDecisionPayload(BaseModel):
    """Body para POST /reports/{id}/decide.

    decision = approved → segue para o próximo estágio.
    decision = requested_changes → volta para needs_revision.
    decision = rejected → bloqueia o report até revisão.
    Comentário obrigatório em requested_changes/rejected.
    """

    decision: ApprovalDecision
    comment: str | None = None


class ApprovalPublic(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    approver_id: uuid.UUID
    stage: ApprovalStage
    decision: ApprovalDecision
    comment: str | None
    decided_at: datetime

    model_config = {"from_attributes": True}


class AIInsightPublic(BaseModel):
    id: uuid.UUID
    scope: Literal["project", "portfolio"]
    project_id: uuid.UUID | None
    report_id: uuid.UUID | None
    agent_run_id: str | None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}
