"""Schemas Pydantic para Report e seus filhos (Risk, ActionPlan, PendingItem,
DeliveryProgress)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import (
    ActionPlanStatus,
    PendingItemStatus,
    ProgressStatus,
    RAGStatus,
    ReportStatus,
    RiskImpact,
    RiskLevel,
    RiskProbability,
    RiskStatus,
)

# ---- linhas filhas ----


class DeliveryProgressIn(BaseModel):
    deliverable_id: uuid.UUID
    status: ProgressStatus = ProgressStatus.PLANNED
    percent_complete: int = Field(ge=0, le=100, default=0)
    comment: str | None = None
    revised_date: date | None = None
    # Persistência da confirmação do modal "Critério de aceite foi atingido?"
    # (spec v3.1 §4.2.2). Obrigatório quando status=done + percent_complete=100.
    acceptance_confirmed: bool | None = None


class DeliveryProgressPublic(DeliveryProgressIn):
    id: uuid.UUID
    deviation_flag: bool = False
    model_config = {"from_attributes": True}


class RiskIn(BaseModel):
    description: str = Field(min_length=1)
    probability: RiskProbability
    impact: RiskImpact
    mitigation_plan: str | None = None
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    status: RiskStatus = RiskStatus.IDENTIFIED


class RiskPublic(RiskIn):
    id: uuid.UUID
    # level é derivado de probability × impact (spec v3.1 §4.2.3); incluído
    # no payload de saída para o frontend exibir sem recomputar.
    # Pydantic com from_attributes=True resolve via property `Risk.level`.
    level: RiskLevel
    model_config = {"from_attributes": True}


class ActionPlanIn(BaseModel):
    description: str = Field(min_length=1)
    objective: str = Field(min_length=1)  # spec v3.1 §4.2.4 — "por que a ação foi criada"
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    status: ActionPlanStatus = ActionPlanStatus.OPEN
    # Vinculações opcionais e independentes (spec v3.1 §4.2.4)
    linked_risk_id: uuid.UUID | None = None
    linked_deliverable_id: uuid.UUID | None = None


class ActionPlanPublic(ActionPlanIn):
    id: uuid.UUID
    # Expansão opcional dos vínculos — preenchida pelo backend quando útil
    # para a UI (ex: revisão do PMO mostrar título do risco/deliverable).
    linked_risk_description: str | None = None
    linked_deliverable_title: str | None = None
    model_config = {"from_attributes": True}


class PendingItemIn(BaseModel):
    description: str = Field(min_length=1)
    owner_party: str | None = None
    due_date: date | None = None
    status: PendingItemStatus = PendingItemStatus.OPEN
    # spec v3.1 §4.2.5 — "se não resolvido, o que afeta"
    impact: str | None = None


class PendingItemPublic(PendingItemIn):
    id: uuid.UUID
    # spec v3.1 §4.2.5 — "Data de abertura: quando foi registrado".
    # Servido como `created_at`; UI pode renderizar com label "Aberto em".
    created_at: datetime
    model_config = {"from_attributes": True}


# ---- Report ----


class ReportCreate(BaseModel):
    project_id: uuid.UUID
    period_start: date
    period_end: date


class ReportPatch(BaseModel):
    """Atualização parcial idempotente — usada pelo autosave do wizard."""

    period_start: date | None = None
    period_end: date | None = None
    # rag_status agregado é derivado pelo backend no submit, mas pode ser
    # enviado pelo cliente para draft.
    rag_status: RAGStatus | None = None
    rag_prazo: RAGStatus | None = None
    rag_escopo: RAGStatus | None = None
    rag_qualidade: RAGStatus | None = None
    rag_prazo_justificativa: str | None = None
    rag_escopo_justificativa: str | None = None
    rag_qualidade_justificativa: str | None = None
    highlights: str | None = None
    next_steps: str | None = None
    notes: str | None = None
    progresses: list[DeliveryProgressIn] | None = None
    risks: list[RiskIn] | None = None
    action_plans: list[ActionPlanIn] | None = None
    pending_items: list[PendingItemIn] | None = None


class ReportPublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    period_start: date
    period_end: date
    rag_status: RAGStatus | None
    rag_prazo: RAGStatus | None = None
    rag_escopo: RAGStatus | None = None
    rag_qualidade: RAGStatus | None = None
    rag_prazo_justificativa: str | None = None
    rag_escopo_justificativa: str | None = None
    rag_qualidade_justificativa: str | None = None
    status: ReportStatus
    highlights: str | None
    next_steps: str | None
    notes: str | None
    health_score: float | None
    created_by_id: uuid.UUID
    created_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    progresses: list[DeliveryProgressPublic] = Field(default_factory=list)
    risks: list[RiskPublic] = Field(default_factory=list)
    action_plans: list[ActionPlanPublic] = Field(default_factory=list)
    pending_items: list[PendingItemPublic] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ReportSummary(BaseModel):
    """Resumo enxuto para listagens (histórico)."""

    id: uuid.UUID
    project_id: uuid.UUID
    period_start: date
    period_end: date
    rag_status: RAGStatus | None
    status: ReportStatus
    created_at: datetime
    submitted_at: datetime | None

    model_config = {"from_attributes": True}
