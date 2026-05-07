"""Schemas Pydantic para o portfólio (Health Score, configuração, dashboard PMO)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import RAGStatus


class HealthScoreComponents(BaseModel):
    progress: float
    risks: float
    pendings: float
    schedule: float


class HealthScorePublic(BaseModel):
    project_id: uuid.UUID
    score: float
    band: Literal["green", "amber", "red"]
    components: HealthScoreComponents
    last_report_id: uuid.UUID | None
    last_report_period_end: date | None


class PortfolioConfigPublic(BaseModel):
    weight_progress: float
    weight_risks: float
    weight_pendings: float
    weight_schedule: float
    updated_at: datetime
    updated_by_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class PortfolioConfigUpdate(BaseModel):
    weight_progress: float = Field(ge=0, le=1)
    weight_risks: float = Field(ge=0, le=1)
    weight_pendings: float = Field(ge=0, le=1)
    weight_schedule: float = Field(ge=0, le=1)


class PortfolioProjectCard(BaseModel):
    project_id: uuid.UUID
    project_name: str
    client_name: str
    gp_user_id: uuid.UUID
    gp_name: str | None
    health: HealthScorePublic
    last_report_rag: RAGStatus | None
    open_risks_count: int
    open_critical_alerts: int
    pending_client_items: int


class PortfolioOverview(BaseModel):
    projects: list[PortfolioProjectCard]
    total_projects: int
    avg_health_score: float | None
    counts_by_band: dict[str, int]
