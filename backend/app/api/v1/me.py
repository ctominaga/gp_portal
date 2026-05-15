"""Endpoints do titular LGPD — exercício dos direitos do art. 18.

`/auth/me` (em auth.py) devolve os dados básicos do JWT.
Este módulo cobre os direitos LGPD propriamente ditos:

  GET  /me/data-export            — direito de portabilidade (art. 18 V).
                                    Retorna ZIP com tudo do titular + log
                                    em DataProcessingRecord (FULFILLED).
  POST /me/data-deletion-request  — direito de eliminação (art. 18 VI).
                                    Cria pedido PENDING + notifica DPO e
                                    devolve recibo neutro ao titular.

A execução do pedido de eliminação fica com o DPO/PMO em
/admin/data-requests/{id}/fulfill (admin_data_requests.py): anonimização
de `User.name/email/password_hash` + carimbo de `anonymized_at`. O texto
livre em Risk/PendingItem/ActionPlan permanece (débito F5.7.X).
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import DataProcessingRecord, DPRequestStatus, DPRequestType, User
from app.schemas.data_request import (
    DataDeletionRequestBody,
    DataProcessingRecordPublic,
)
from app.services.data_export_service import build_export_zip
from app.services.notifications import _send_email

router = APIRouter(prefix="/me", tags=["me-lgpd"])

# Canal LGPD operacional. Christopher Tominaga é o DPO designado/signatário
# e atua como receptor operacional direto dos pedidos enquanto o alias
# lgpd@jumplabel.com.br não é provisionado (débito F5.7.Z). Hardcode
# documentado como débito de hardening F5.9.X (refactor para env var
# DPO_NOTIFICATION_EMAIL fica para F6).
_DPO_OPERATIONAL_EMAIL = "christopher.tominaga@jumplabel.com.br"


def _zip_filename(user: User, now: datetime) -> str:
    """Nome estável e identificável: `jump-lgpd-export-{user-id}-{YYYYMMDD}.zip`.

    Usa o id (UUID) em vez do e-mail no nome do arquivo para evitar criar
    um cabeçalho que pode acabar em logs de servidor/proxy. Histórico completo
    da extração fica no DataProcessingRecord.
    """
    stamp = now.strftime("%Y%m%d")
    return f"jump-lgpd-export-{user.id}-{stamp}.zip"


@router.get("/data-export")
async def data_export(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Exporta dados pessoais do titular autenticado (LGPD art. 18 V).

    Cria um DataProcessingRecord síncrono como evidência da operação
    (status=FULFILLED, request_type=EXPORT, fulfilled_at=now()). O log
    é gravado DEPOIS do snapshot — não aparece no ZIP atual, mas vai
    aparecer no próximo export (auditoria recursiva).
    """
    payload = await build_export_zip(db, user)
    now = datetime.now(UTC)

    record = DataProcessingRecord(
        subject_user_id=user.id,
        request_type=DPRequestType.EXPORT,
        status=DPRequestStatus.FULFILLED,
        requested_at=now,
        fulfilled_at=now,
        handled_by_id=user.id,
        notes="Exportação automática via GET /me/data-export.",
    )
    db.add(record)
    await db.commit()

    filename = _zip_filename(user, now)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(len(payload)),
    }

    def _iter():
        yield payload

    return StreamingResponse(
        _iter(), media_type="application/zip", headers=headers
    )


# Recibo neutro pro titular — não promete outcome (art. 18 §3º LGPD permite
# que o DPO negue eliminações cobertas por base legal de retenção). O texto
# replica a frase escolhida no ADR F5.7 abertura (Q3): "Pedido recebido,
# retornaremos em até 15 dias úteis."
_RECEIPT_SUBJECT = "Pedido recebido"
_RECEIPT_BODY = "Pedido recebido, retornaremos em até 15 dias úteis."


@router.post(
    "/data-deletion-request",
    response_model=DataProcessingRecordPublic,
    status_code=status.HTTP_201_CREATED,
)
async def request_data_deletion(
    payload: DataDeletionRequestBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataProcessingRecord:
    """Titular logado registra pedido de eliminação (LGPD art. 18 VI).

    Não anonimiza nada aqui — só cria o registro PENDING e dispara as duas
    notificações (DPO + recibo neutro). A anonimização efetiva fica com o
    DPO/PMO via `POST /admin/data-requests/{id}/fulfill` depois da análise
    do caso (LGPD art. 18 §4º — pode haver dever de retenção concorrente).
    """
    record = DataProcessingRecord(
        subject_user_id=user.id,
        request_type=DPRequestType.DELETION,
        status=DPRequestStatus.PENDING,
        notes=payload.notes,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    # Notificação ao DPO: dado mínimo necessário para abrir o caso. Sem
    # PII além do que o DPO já tem direito a ver (id + e-mail do titular,
    # nota do pedido).
    dpo_subject = f"[LGPD] Pedido de eliminação — {user.email}"
    dpo_body = (
        f"Titular {user.name} <{user.email}> (id={user.id}) registrou "
        f"pedido de eliminação via /me/data-deletion-request em "
        f"{record.requested_at.isoformat()}. "
        f"Pedido id={record.id}. "
        f"Notas: {payload.notes or '(sem nota)'}"
    )
    _send_email(to=_DPO_OPERATIONAL_EMAIL, subject=dpo_subject, body=dpo_body)
    _send_email(to=user.email, subject=_RECEIPT_SUBJECT, body=_RECEIPT_BODY)

    return record


__all__ = ["router"]
