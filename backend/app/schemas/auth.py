"""Schemas Pydantic para o módulo de autenticação."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_s: int
    user: UserPublic


class UserPublic(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: Role
    created_at: datetime

    model_config = {"from_attributes": True}


TokenResponse.model_rebuild()
