"""Segurança: JWT + bcrypt."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.models.user import Role

_settings = get_settings()
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_ctx.verify(plain, hashed)
    except ValueError:
        return False


def create_access_token(*, sub: uuid.UUID, role: Role, expires_hours: int | None = None) -> str:
    expires = expires_hours if expires_hours is not None else _settings.jwt_expires_hours
    now = datetime.now(UTC)
    payload = {
        "sub": str(sub),
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires)).timestamp()),
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decodifica e valida assinatura/expiração. Levanta JWTError em falha."""
    return jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])


__all__ = [
    "JWTError",
    "create_access_token",
    "decode_token",
    "hash_password",
    "verify_password",
]
