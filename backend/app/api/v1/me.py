"""Endpoints do titular LGPD — exercício dos direitos do art. 18.

`/auth/me` (em auth.py) devolve os dados básicos do JWT.
Este módulo cobre os direitos LGPD propriamente ditos:

  GET /me/data-export — direito de portabilidade (art. 18 V).
                        Retorna ZIP com tudo do titular + log síncrono
                        em DataProcessingRecord (status=FULFILLED).

Commit 3 adicionará POST /me/data-deletion-request.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import DataProcessingRecord, DPRequestStatus, DPRequestType, User
from app.services.data_export_service import build_export_zip

router = APIRouter(prefix="/me", tags=["me-lgpd"])


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


__all__ = ["router"]
