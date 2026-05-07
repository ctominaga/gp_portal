"""Schemas Pydantic para Baseline + Deliverable."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import BaselineStatus, DeliverableComplexity


class DeliverablePublic(BaseModel):
    id: uuid.UUID
    code: str | None
    title: str
    description: str | None
    phase: str | None
    category: str | None
    complexity: DeliverableComplexity | None
    source_excerpt: str | None
    due_date: date | None
    order_index: int

    model_config = {"from_attributes": True}


class DeliverableUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    phase: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    complexity: DeliverableComplexity | None = None
    source_excerpt: str | None = None
    due_date: date | None = None
    order_index: int | None = None


class DeliverableCreate(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    phase: str | None = None
    category: str | None = None
    complexity: DeliverableComplexity | None = None
    source_excerpt: str | None = None
    due_date: date | None = None
    order_index: int = 0


class BaselinePublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    proposal_id: uuid.UUID
    status: BaselineStatus
    activated_at: datetime | None
    activated_by_id: uuid.UUID | None
    payload: dict[str, Any]
    created_at: datetime
    deliverables: list[DeliverablePublic]

    model_config = {"from_attributes": True}
