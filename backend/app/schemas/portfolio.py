"""Schemas Pydantic para o portfólio (Health Score, configuração, dashboard PMO)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models import RAGStatus


class HealthScoreComponents(BaseModel):
    """5 componentes do Health Score (spec v3.1 §10.3), cada um em [0..100]."""

    rag_avg: float
    spi: float
    risk_inverse: float
    resolution_rate: float
    stability: float


class HealthScorePublic(BaseModel):
    project_id: uuid.UUID
    score: float
    band: Literal["green", "amber", "red"]
    components: HealthScoreComponents
    weights_applied: dict[str, float] | None = None
    last_report_id: uuid.UUID | None
    last_report_period_end: date | None


class HealthScoreWeights(BaseModel):
    """Pesos dos 5 componentes do Health Score (spec v3.1 §10.3).

    Defaults ancorados na spec: 35/25/20/10/10. Soma esperada = 1.00 ± 0.01.
    """

    rag_avg: float = Field(ge=0, le=1)
    spi: float = Field(ge=0, le=1)
    risk_inverse: float = Field(ge=0, le=1)
    resolution_rate: float = Field(ge=0, le=1)
    stability: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _check_sum(self) -> "HealthScoreWeights":
        total = (
            self.rag_avg
            + self.spi
            + self.risk_inverse
            + self.resolution_rate
            + self.stability
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"soma dos pesos deve ser 1.00 ± 0.01 (atual: {total:.4f})"
            )
        return self


class PortfolioConfigPublic(BaseModel):
    health_score_weights: dict[str, float]
    updated_at: datetime
    updated_by_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class PortfolioConfigUpdate(BaseModel):
    """Payload do PUT/PATCH /portfolio/config. Valida soma=1.00 ± 0.01."""

    health_score_weights: HealthScoreWeights


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
