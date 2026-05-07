"""Schemas Pydantic para o Portal do Cliente."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models import RAGStatus, ReportStatus


class ClientPendingItem(BaseModel):
    description: str
    due_date: date | None
    owner_party: str | None


class ClientReportPublic(BaseModel):
    id: uuid.UUID
    period_start: date
    period_end: date
    rag_status: RAGStatus | None
    status: ReportStatus
    highlights: str | None
    next_steps: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    pending_items: list[ClientPendingItem]


class ClientProjectView(BaseModel):
    id: uuid.UUID
    name: str
    client_name: str
    status: str
    started_at: date | None
    latest_rag: RAGStatus | None
    health_score: float | None
    open_pending_items: int
    open_risks_count: int
    reports: list[ClientReportPublic]


class ScopeChangePublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    description: str
    requested_at: datetime
    decided_at: datetime | None
    status: str
    impact_baseline_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class BaselineDiffEntry(BaseModel):
    kind: str  # added | removed | changed
    code: str | None
    title_old: str | None
    title_new: str | None
    phase_old: str | None
    phase_new: str | None
    complexity_old: str | None
    complexity_new: str | None


class BaselineDiffResponse(BaseModel):
    base_baseline_id: uuid.UUID
    new_baseline_id: uuid.UUID
    added: list[BaselineDiffEntry]
    removed: list[BaselineDiffEntry]
    changed: list[BaselineDiffEntry]
    scope_changes_created: int
