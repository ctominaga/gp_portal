"""Endpoints de Baseline + Deliverable usados pela revisão (F3.4)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import (
    Baseline,
    BaselineStatus,
    Deliverable,
    Project,
    Role,
    User,
)
from app.schemas.baseline import (
    BaselinePublic,
    DeliverableCreate,
    DeliverablePublic,
    DeliverableUpdate,
)

router = APIRouter(tags=["baselines"])


async def _load_baseline_for_user(
    baseline_id: uuid.UUID, user: User, db: AsyncSession
) -> Baseline:
    baseline = (
        await db.execute(select(Baseline).where(Baseline.id == baseline_id))
    ).scalar_one_or_none()
    if not baseline:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "baseline não encontrada")
    project = await db.get(Project, baseline.project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto da baseline não encontrado")
    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")
    if user.role == Role.CLIENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cliente não acessa baseline")
    return baseline


async def _load_deliverables(
    baseline_id: uuid.UUID, db: AsyncSession
) -> list[Deliverable]:
    rows = (
        await db.execute(
            select(Deliverable)
            .where(Deliverable.baseline_id == baseline_id)
            .order_by(Deliverable.order_index, Deliverable.created_at)
        )
    ).scalars().all()
    return list(rows)


def _serialize_baseline(b: Baseline, deliverables: list[Deliverable]) -> dict:
    return {
        "id": b.id,
        "project_id": b.project_id,
        "proposal_id": b.proposal_id,
        "status": b.status,
        "activated_at": b.activated_at,
        "activated_by_id": b.activated_by_id,
        "payload": b.payload or {},
        "created_at": b.created_at,
        "deliverables": [
            DeliverablePublic.model_validate(d, from_attributes=True) for d in deliverables
        ],
    }


@router.get("/baselines/{baseline_id}", response_model=BaselinePublic)
async def get_baseline(
    baseline_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP, Role.PMO, Role.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> BaselinePublic:
    baseline = await _load_baseline_for_user(baseline_id, user, db)
    deliverables = await _load_deliverables(baseline.id, db)
    return BaselinePublic.model_validate(_serialize_baseline(baseline, deliverables))


@router.post(
    "/baselines/{baseline_id}/deliverables",
    response_model=DeliverablePublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_deliverable(
    baseline_id: uuid.UUID,
    payload: DeliverableCreate,
    user: User = Depends(require_any_role(Role.GP)),
    db: AsyncSession = Depends(get_db),
) -> Deliverable:
    baseline = await _load_baseline_for_user(baseline_id, user, db)
    if baseline.status != BaselineStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "só é possível adicionar entregáveis em baseline draft",
        )
    deliv = Deliverable(baseline_id=baseline.id, **payload.model_dump(exclude_unset=True))
    db.add(deliv)
    await db.commit()
    await db.refresh(deliv)
    return deliv


@router.patch(
    "/deliverables/{deliverable_id}",
    response_model=DeliverablePublic,
)
async def update_deliverable(
    deliverable_id: uuid.UUID,
    payload: DeliverableUpdate,
    user: User = Depends(require_any_role(Role.GP)),
    db: AsyncSession = Depends(get_db),
) -> Deliverable:
    deliv = await db.get(Deliverable, deliverable_id)
    if not deliv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entregável não encontrado")
    baseline = await _load_baseline_for_user(deliv.baseline_id, user, db)
    if baseline.status != BaselineStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "só é possível editar entregáveis em baseline draft",
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(deliv, k, v)
    await db.commit()
    await db.refresh(deliv)
    return deliv


@router.delete(
    "/deliverables/{deliverable_id}",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_deliverable(
    deliverable_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    deliv = await db.get(Deliverable, deliverable_id)
    if not deliv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entregável não encontrado")
    baseline = await _load_baseline_for_user(deliv.baseline_id, user, db)
    if baseline.status != BaselineStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "só é possível remover entregáveis em baseline draft",
        )
    await db.delete(deliv)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/baselines/{baseline_id}/activate",
    response_model=BaselinePublic,
)
async def activate_baseline(
    baseline_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP)),
    db: AsyncSession = Depends(get_db),
) -> BaselinePublic:
    baseline = await _load_baseline_for_user(baseline_id, user, db)
    if baseline.status == BaselineStatus.ACTIVE:
        # idempotente
        return BaselinePublic.model_validate(
            _serialize_baseline(baseline, await _load_deliverables(baseline.id, db))
        )
    if baseline.status != BaselineStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"baseline em {baseline.status.value} não pode ser ativada",
        )

    # Marca os outros baselines do projeto como superseded
    await db.execute(
        update(Baseline)
        .where(
            Baseline.project_id == baseline.project_id,
            Baseline.id != baseline.id,
            Baseline.status == BaselineStatus.ACTIVE,
        )
        .values(status=BaselineStatus.SUPERSEDED)
    )

    baseline.status = BaselineStatus.ACTIVE
    baseline.activated_at = datetime.now(UTC)
    baseline.activated_by_id = user.id
    await db.commit()
    await db.refresh(baseline)

    deliverables = await _load_deliverables(baseline.id, db)
    return BaselinePublic.model_validate(_serialize_baseline(baseline, deliverables))


@router.get(
    "/projects/{project_id}/active-baseline",
    response_model=BaselinePublic | None,
)
async def get_active_baseline(
    project_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP, Role.PMO, Role.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> BaselinePublic | None:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")
    baseline = (
        await db.execute(
            select(Baseline).where(
                Baseline.project_id == project_id,
                Baseline.status == BaselineStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if not baseline:
        return None
    deliverables = await _load_deliverables(baseline.id, db)
    return BaselinePublic.model_validate(_serialize_baseline(baseline, deliverables))
