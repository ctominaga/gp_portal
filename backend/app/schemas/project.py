"""Schemas Pydantic para Projects e Proposals."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import ProjectStatus, ProposalStatus


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    client_name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    started_at: date | None = None
    client_user_email: EmailStr | None = None  # cliente precisa estar registrado para virar FK


class ProjectPublic(BaseModel):
    id: uuid.UUID
    name: str
    client_name: str
    description: str | None
    gp_user_id: uuid.UUID
    client_user_id: uuid.UUID | None
    status: ProjectStatus
    started_at: date | None
    ended_at: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProposalPublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    file_url: str
    original_filename: str
    size_bytes: int
    status: ProposalStatus
    uploaded_by_id: uuid.UUID
    uploaded_at: datetime

    model_config = {"from_attributes": True}
