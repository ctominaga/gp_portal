"""Schemas Pydantic da retrospectiva (F5.3 — v3.1 §10.4).

Sustenta o fluxo:
  GP preenche retrospectiva → POST /projects/{id}/close → backend valida
  cascata de bloqueios + cria ProjectRetrospective + marca Project.status=CLOSED.

A validação FK de `materialized_risks[*].risk_id` é feita **no endpoint**
(precisa de query ao banco), não no schema Pydantic — Pydantic não tem
acesso natural à AsyncSession. Schema valida só tipos e min_length.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import ProjectStatus


class MaterializedRiskItem(BaseModel):
    """Item de `materialized_risks` no body do POST /close.

    `risk_id` deve referenciar um Risk existente que pertence ao projeto
    sendo encerrado (FK validation no endpoint). `comment` é a descrição
    livre de "como foi tratado" — opcional, pode ser None.
    """

    risk_id: uuid.UUID
    comment: str | None = None


class RetrospectiveCreate(BaseModel):
    """Body do POST /projects/{id}/close (spec v3.1 §10.4).

    Os 3 campos textuais são obrigatórios (NOT NULL no modelo, min_length=1
    após strip implícito do Pydantic). `materialized_risks` aceita lista
    vazia — "nenhum risco materializou" é cenário ideal e válido.
    """

    delivered_vs_proposed: str = Field(..., min_length=1)
    would_do_differently: str = Field(..., min_length=1)
    client_feedback: str = Field(..., min_length=1)
    materialized_risks: list[MaterializedRiskItem] = Field(default_factory=list)


class RetrospectivePublic(BaseModel):
    """Representação read-only do `GET /projects/{id}/retrospective`."""

    id: uuid.UUID
    project_id: uuid.UUID
    delivered_vs_proposed: str
    would_do_differently: str
    client_feedback: str
    materialized_risks: list[MaterializedRiskItem] = Field(default_factory=list)
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCloseResult(BaseModel):
    """Resposta do POST /projects/{id}/close.

    Empacota a transição de estado + a retrospectiva recém-criada em um
    payload único para o frontend não precisar fazer 2 requests.
    """

    project_id: uuid.UUID
    status: ProjectStatus
    ended_at: date
    retrospective: RetrospectivePublic
