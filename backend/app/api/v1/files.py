"""Endpoint de signed URLs para o backend LocalStorage.

Em produção com R2, esses URLs são gerados pelo próprio R2 (boto3
generate_presigned_url) e não passam por aqui.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from jump_storage import verify_local_signature
from jump_storage.factory import get_storage
from jump_storage.local import LocalStorage

from app.core.config import get_settings

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/signed/{token}/{exp}/{key:path}")
async def get_signed_file(token: str, exp: int, key: str) -> Response:
    """Verifica HMAC + expiração e devolve o conteúdo."""
    secret = get_settings().jwt_secret  # mesmo segredo da fábrica
    if not verify_local_signature(token, key, exp, secret):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "assinatura inválida ou expirada")

    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "rota /files/signed/* só faz sentido em LocalStorage",
        )
    try:
        data = storage.get(key)
    except Exception as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return Response(content=data, media_type="application/octet-stream")
