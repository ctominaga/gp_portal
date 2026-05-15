"""DTOs do fluxo LGPD direitos do titular (F5.7).

Cobre os 3 endpoints novos do Commit 3:
  POST /me/data-deletion-request — corpo do pedido de eliminação criado
                                   pelo próprio titular.
  POST /admin/data-requests       — criação manual pelo DPO/PMO a partir
                                   de e-mail externo.
  GET  /admin/data-requests       — listagem paginada.

`DataProcessingRecordPublic` é a representação canônica do registro RAT
para o frontend (espelha o modelo SQL `DataProcessingRecord` com nomes
estáveis e enums serializados pelo valor).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DPRequestStatus, DPRequestType


class DataDeletionRequestBody(BaseModel):
    """Body de POST /me/data-deletion-request — opcionalmente uma nota livre
    ("motivo do pedido"). Não há campo de "outcome esperado" porque a
    decisão fica com o DPO no exame do caso concreto (LGPD art. 18 §3º)."""

    notes: str | None = Field(default=None, max_length=2000)


class AdminDataRequestCreate(BaseModel):
    """Body de POST /admin/data-requests — criação manual a partir de pedido
    externo (e-mail enviado ao canal LGPD, formulário fora do sistema, etc.).

    Casos internos passam pelos endpoints próprios do titular logado
    (`/me/data-export`, `/me/data-deletion-request`).
    """

    subject_external_email: EmailStr
    request_type: DPRequestType
    notes: str | None = Field(default=None, max_length=2000)


class DataProcessingRecordPublic(BaseModel):
    """Espelha `DataProcessingRecord` para o frontend. Enums saem como string
    (valor) graças ao serializador default do Pydantic v2."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_user_id: uuid.UUID | None
    subject_external_email: str | None
    request_type: DPRequestType
    status: DPRequestStatus
    requested_at: datetime
    fulfilled_at: datetime | None
    handled_by_id: uuid.UUID | None
    notes: str | None


class DataProcessingRecordList(BaseModel):
    """Resposta paginada de GET /admin/data-requests."""

    items: list[DataProcessingRecordPublic]
    total: int
    page: int
    page_size: int


__all__ = [
    "AdminDataRequestCreate",
    "DataDeletionRequestBody",
    "DataProcessingRecordList",
    "DataProcessingRecordPublic",
]
