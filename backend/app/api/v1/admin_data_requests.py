"""Endpoints admin para o RAT LGPD (F5.7 commit 3).

Role-gated a PMO. Cobre:

  POST /admin/data-requests              — criação manual a partir de pedido
                                           externo recebido fora do sistema
                                           (e-mail no canal LGPD, formulário
                                           físico, etc.).
  GET  /admin/data-requests              — listagem paginada com filtros.
  POST /admin/data-requests/{id}/fulfill — atende o pedido. Para DELETION
                                           com subject_user_id presente,
                                           anonimiza o User (name/email/
                                           password_hash zerados + carimbo
                                           anonymized_at). Idempotente.

Tudo fica em /admin/data-requests para não conflitar com /me (titular).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models import (
    DataProcessingRecord,
    DPRequestStatus,
    DPRequestType,
    Role,
    User,
)
from app.schemas.data_request import (
    AdminDataRequestCreate,
    DataProcessingRecordList,
    DataProcessingRecordPublic,
)

router = APIRouter(prefix="/admin/data-requests", tags=["admin-lgpd"])


_ANON_NAME = "Titular removido"


def _anon_email(user_id: uuid.UUID) -> str:
    """Email pós-anonimização. Domínio `.local` para sinalizar não-roteável
    e impedir colisão com endereço real (RFC 6762 / RFC 2606). Mantém
    UNIQUE constraint da tabela `users` funcionando."""
    return f"anonymized_{user_id}@removed.local"


@router.post(
    "",
    response_model=DataProcessingRecordPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_request(
    payload: AdminDataRequestCreate,
    pmo: User = Depends(require_role(Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> DataProcessingRecord:
    """DPO/PMO registra um pedido vindo por canal externo (e-mail).

    Caso interno (titular logado) usa POST /me/data-deletion-request.
    O `handled_by_id` fica nulo aqui — só vira o id do PMO no fulfill.
    """
    record = DataProcessingRecord(
        subject_user_id=None,
        subject_external_email=payload.subject_external_email.lower(),
        request_type=payload.request_type,
        status=DPRequestStatus.PENDING,
        notes=payload.notes,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("", response_model=DataProcessingRecordList)
async def list_requests(
    status_filter: DPRequestStatus | None = Query(default=None, alias="status"),
    request_type: DPRequestType | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _pmo: User = Depends(require_role(Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> DataProcessingRecordList:
    """Listagem paginada para a tela /admin/data-requests no frontend."""
    base_filters = []
    if status_filter is not None:
        base_filters.append(DataProcessingRecord.status == status_filter)
    if request_type is not None:
        base_filters.append(DataProcessingRecord.request_type == request_type)

    total = (
        await db.execute(
            select(func.count(DataProcessingRecord.id)).where(*base_filters)
        )
    ).scalar_one()

    offset = (page - 1) * page_size
    rows = list(
        (
            await db.execute(
                select(DataProcessingRecord)
                .where(*base_filters)
                .order_by(DataProcessingRecord.requested_at.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).scalars().all()
    )
    return DataProcessingRecordList(
        items=[DataProcessingRecordPublic.model_validate(r) for r in rows],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{record_id}/fulfill", response_model=DataProcessingRecordPublic
)
async def fulfill_request(
    record_id: uuid.UUID,
    pmo: User = Depends(require_role(Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> DataProcessingRecord:
    """Marca um pedido como atendido. Para DELETION com `subject_user_id`
    presente, executa a anonimização (Q1 do ADR F5.7 abertura).

    Idempotente: chamar de novo em um registro FULFILLED é no-op (devolve
    o registro inalterado). Se o User já está anonimizado (anonymized_at
    setado), só marca o request como FULFILLED sem reaplicar os zeros.
    """
    record = await db.get(DataProcessingRecord, record_id)
    if not record:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "pedido não encontrado"
        )

    if record.status == DPRequestStatus.FULFILLED:
        return record

    now = datetime.now(UTC)

    if (
        record.request_type == DPRequestType.DELETION
        and record.subject_user_id is not None
    ):
        subject = await db.get(User, record.subject_user_id)
        if subject is not None and subject.anonymized_at is None:
            subject.name = _ANON_NAME
            subject.email = _anon_email(subject.id)
            subject.password_hash = ""
            subject.anonymized_at = now

    record.status = DPRequestStatus.FULFILLED
    record.fulfilled_at = now
    record.handled_by_id = pmo.id
    await db.commit()
    await db.refresh(record)
    return record


__all__ = ["router"]
