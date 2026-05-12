"""Schemas Pydantic para versionamento de escopo (F5.2 — v3.1 §10.5).

Sustenta o fluxo:
  GP faz upload de proposta v2 → worker importa + cria baseline DRAFT v2 +
  ScopeChanges PROPOSED via `diff_baselines` → PMO revisa e aprova/rejeita
  a transição inteira via POST /baselines/{id}/transition.

Granularidade: 1 ScopeChange por entregável afetado (ADDED/REMOVED/MODIFIED).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from app.models import ScopeChangeStatus, ScopeChangeType


class ScopeChangePublic(BaseModel):
    """Representação read-only de um ScopeChange (GET /projects/{id}/scope-changes
    e GET /scope-changes/{id})."""

    id: uuid.UUID
    project_id: uuid.UUID
    description: str
    change_type: ScopeChangeType | None
    deliverable_code: str | None
    baseline_from_id: uuid.UUID | None
    baseline_to_id: uuid.UUID | None
    status: ScopeChangeStatus
    requested_at: datetime
    decided_at: datetime | None
    approved_by_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class TransitionDecisionPayload(BaseModel):
    """Body do POST /baselines/{id}/transition.

    Aprovação é em **batch**: todos os ScopeChanges PROPOSED com
    `baseline_to_id = {id}` mudam de status juntos. Não há aprovação
    item-a-item (vide spec v3.1 §10.5 + decisão Q1 do plano F5.2).

    Validação F5.2 commit 5 (ADR em `docs/decisoes.md`):
      - `decision == "reject"` exige `comment` não-vazio (após strip).
        GP precisa saber por que ressubmeter; sem justificativa, a
        rejeição é uma caixa-preta. Pydantic levanta ValidationError
        (FastAPI converte em 422).
      - `decision == "approve"` aceita `comment` vazio ou ausente —
        aprovação tácita é caso de uso legítimo (PMO acompanhou
        a evolução em reunião).
    """

    decision: Literal["approve", "reject"]
    comment: str | None = None

    @model_validator(mode="after")
    def _require_reject_comment(self) -> "TransitionDecisionPayload":
        if self.decision == "reject":
            if not self.comment or not self.comment.strip():
                raise ValueError(
                    "comment é obrigatório (não-vazio após strip) quando "
                    "decision='reject' — GP precisa da justificativa para "
                    "ressubmeter."
                )
        return self


class TransitionResult(BaseModel):
    """Resposta do POST /baselines/{id}/transition."""

    baseline_id: uuid.UUID
    baseline_status: str
    decision: Literal["approve", "reject"]
    scope_changes_count: int
    decided_at: datetime
    approved_by: uuid.UUID
