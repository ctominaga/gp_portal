"""Endpoints read-only de ScopeChange (F5.2 — v3.1 §10.5).

A escrita acontece em outros lugares:
  - `diff_baselines` (worker, em `client_portal.py`) cria os PROPOSED quando
    proposta v2+ é importada.
  - `POST /baselines/{id}/transition` (em `baselines.py`) move em batch
    para IMPLEMENTED ou REJECTED quando o PMO decide.

Aqui só listamos e detalhamos, para o PMO revisar e o frontend exibir.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import (
    Project,
    Role,
    ScopeChange,
    ScopeChangeStatus,
    User,
)
from app.schemas.scope_change import ScopeChangePublic

router = APIRouter(tags=["scope_changes"])


@router.get(
    "/projects/{project_id}/scope-changes",
    response_model=list[ScopeChangePublic],
)
async def list_project_scope_changes(
    project_id: uuid.UUID,
    status_filter: ScopeChangeStatus = Query(
        default=ScopeChangeStatus.PROPOSED, alias="status"
    ),
    baseline_to_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(require_any_role(Role.GP, Role.PMO, Role.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> list[ScopeChange]:
    """Lista ScopeChanges de um projeto. Filtro default: PROPOSED.

    GP só vê do próprio projeto. PMO/OPERATOR veem todos.
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")

    stmt = select(ScopeChange).where(
        ScopeChange.project_id == project_id,
        ScopeChange.status == status_filter,
    )
    if baseline_to_id is not None:
        stmt = stmt.where(ScopeChange.baseline_to_id == baseline_to_id)
    stmt = stmt.order_by(ScopeChange.requested_at.desc())

    return list((await db.execute(stmt)).scalars().all())


@router.get("/scope-changes/{scope_change_id}", response_model=ScopeChangePublic)
async def get_scope_change(
    scope_change_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP, Role.PMO, Role.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> ScopeChange:
    sc = await db.get(ScopeChange, scope_change_id)
    if not sc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scope change não encontrado")
    project = await db.get(Project, sc.project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")
    return sc
