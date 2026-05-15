"""Endpoints de autenticação."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import Role, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    """Seed-only em F2: usado pelo seeder. Em prod ficará atrás de auth."""
    # Normalizar email para lowercase no exists-check também — armazenamos
    # com lower() e login filtra por lower(). Sem essa normalização, payload
    # com case misto (ex: "GP-A@x.com") passa pelo SELECT, segue para INSERT
    # com lowercase, e dispara IntegrityError em vez de 409 explícito.
    # Descoberto em F5.3 commit 2.
    normalized_email = payload.email.lower()
    exists = (
        await db.execute(select(User).where(User.email == normalized_email))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "email já registrado")
    user = User(
        name=payload.name,
        email=normalized_email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    # F5.7 LGPD login guard: usuários anonimizados retornam o MESMO texto
    # de credenciais inválidas. Vazar "esta conta foi anonimizada" daria
    # ao invasor uma sonda para descobrir titulares que pediram eliminação.
    # Após anonimização, password_hash="" também garante que verify_password
    # falharia naturalmente — o guard explícito é cinto-e-suspensórios.
    if (
        not user
        or user.anonymized_at is not None
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "credenciais inválidas")

    token = create_access_token(sub=user.id, role=user.role)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_s=_settings.jwt_expires_hours * 3600,
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


__all__ = ["router", "Role"]
