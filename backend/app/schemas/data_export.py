"""DTOs do export LGPD (GET /me/data-export).

Cada arquivo do ZIP é serializado a partir destes modelos via
`model_dump(mode='json')` no serviço. A separação `ProjectAsGp` /
`ProjectAsClient` corresponde aos dois papéis pelos quais um titular
pode ter dados no Sistema; o filtro CLIENT (apenas Reports liberados e
Approvals próprias, sem AgentRunLog) está implementado no serviço, não no
schema — schemas refletem a forma do JSON, regras de minimização ficam
no `data_export_service`.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr


_FROM_ATTRS = ConfigDict(from_attributes=True)


class UserExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    created_at: datetime
    anonymized_at: datetime | None


class DeliverableExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    code: str | None
    title: str
    description: str | None
    phase: str | None
    category: str | None
    complexity: str | None
    type: str | None
    due_date: date | None
    status: str
    acceptance_criteria: str | None
    order_index: int
    created_at: datetime


class BaselineExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    proposal_id: uuid.UUID
    status: str
    activated_at: datetime | None
    payload: dict
    created_at: datetime
    deliverables: list[DeliverableExport] = []


class RiskExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    description: str
    probability: str
    impact: str
    mitigation_plan: str | None
    owner_id: uuid.UUID | None
    due_date: date | None
    status: str
    created_at: datetime


class PendingItemExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    description: str
    owner_party: str | None
    due_date: date | None
    status: str
    impact: str | None
    created_at: datetime


class ActionPlanExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    description: str
    objective: str
    owner_id: uuid.UUID | None
    due_date: date | None
    status: str
    linked_risk_id: uuid.UUID | None
    linked_deliverable_id: uuid.UUID | None


class DeliveryProgressExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    deliverable_id: uuid.UUID
    status: str
    percent_complete: int
    comment: str | None
    revised_date: date | None
    acceptance_confirmed: bool | None


class ApprovalExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    report_id: uuid.UUID
    approver_id: uuid.UUID
    stage: str
    decision: str
    comment: str | None
    decided_at: datetime


class ReportExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    project_id: uuid.UUID
    period_start: date
    period_end: date
    status: str
    rag_status: str | None
    rag_prazo: str | None
    rag_escopo: str | None
    rag_qualidade: str | None
    highlights: str | None
    next_steps: str | None
    notes: str | None
    health_score: float | None
    created_by_id: uuid.UUID
    created_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    risks: list[RiskExport] = []
    pending_items: list[PendingItemExport] = []
    action_plans: list[ActionPlanExport] = []
    delivery_progresses: list[DeliveryProgressExport] = []


class ScopeChangeExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    description: str
    baseline_from_id: uuid.UUID | None
    baseline_to_id: uuid.UUID | None
    change_type: str | None
    deliverable_code: str | None
    status: str
    requested_at: datetime
    decided_at: datetime | None
    approved_by_id: uuid.UUID | None


class AgentRunLogExport(BaseModel):
    model_config = _FROM_ATTRS

    run_id: str
    task_type: str
    project_id: uuid.UUID | None
    proposal_id: uuid.UUID | None
    report_id: uuid.UUID | None
    engine_used: str | None
    route_used: str | None
    status: str
    duration_s: float | None
    created_at: datetime
    completed_at: datetime | None


class ProjectAsGpExport(BaseModel):
    """Visão completa dos projetos onde o titular é o GP responsável."""

    model_config = _FROM_ATTRS

    id: uuid.UUID
    name: str
    client_name: str
    description: str | None
    status: str
    started_at: date | None
    ended_at: date | None
    health_score_cached: float | None
    created_at: datetime
    baselines: list[BaselineExport] = []
    reports: list[ReportExport] = []
    approvals: list[ApprovalExport] = []
    scope_changes: list[ScopeChangeExport] = []
    agent_run_logs: list[AgentRunLogExport] = []


class ProjectAsClientExport(BaseModel):
    """Visão minimizada para o cliente. Sem AgentRunLog, sem baselines, sem
    scope_changes — só os artefatos publicados (Reports liberados/arquivados)
    e suas próprias decisões (Approvals em que o titular foi o aprovador).
    """

    model_config = _FROM_ATTRS

    id: uuid.UUID
    name: str
    client_name: str
    description: str | None
    status: str
    started_at: date | None
    ended_at: date | None
    reports: list[ReportExport] = []
    approvals: list[ApprovalExport] = []


class DataProcessingRecordExport(BaseModel):
    model_config = _FROM_ATTRS

    id: uuid.UUID
    request_type: str
    status: str
    requested_at: datetime
    fulfilled_at: datetime | None
    notes: str | None


__all__ = [
    "ActionPlanExport",
    "AgentRunLogExport",
    "ApprovalExport",
    "BaselineExport",
    "DataProcessingRecordExport",
    "DeliverableExport",
    "DeliveryProgressExport",
    "PendingItemExport",
    "ProjectAsClientExport",
    "ProjectAsGpExport",
    "ReportExport",
    "RiskExport",
    "ScopeChangeExport",
    "UserExport",
]
