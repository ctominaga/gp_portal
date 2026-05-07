"""Endpoints de Report — CRUD + PATCH idempotente para autosave do wizard."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import (
    ActionPlan,
    DeliveryProgress,
    PendingItem,
    Project,
    Report,
    ReportStatus,
    Risk,
    Role,
    User,
)
from app.schemas.report import (
    ActionPlanPublic,
    DeliveryProgressPublic,
    PendingItemPublic,
    ReportCreate,
    ReportPatch,
    ReportPublic,
    ReportSummary,
    RiskPublic,
)

router = APIRouter(tags=["reports"])


async def _ensure_project_owned(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")
    return project


async def _serialize_report(report: Report, db: AsyncSession) -> ReportPublic:
    """Carrega filhos do report e serializa."""
    progresses = list(
        (
            await db.execute(
                select(DeliveryProgress).where(DeliveryProgress.report_id == report.id)
            )
        ).scalars().all()
    )
    risks = list(
        (
            await db.execute(select(Risk).where(Risk.report_id == report.id))
        ).scalars().all()
    )
    action_plans = list(
        (
            await db.execute(select(ActionPlan).where(ActionPlan.report_id == report.id))
        ).scalars().all()
    )
    pending_items = list(
        (
            await db.execute(select(PendingItem).where(PendingItem.report_id == report.id))
        ).scalars().all()
    )

    return ReportPublic(
        id=report.id,
        project_id=report.project_id,
        period_start=report.period_start,
        period_end=report.period_end,
        rag_status=report.rag_status,
        status=report.status,
        highlights=report.highlights,
        next_steps=report.next_steps,
        notes=report.notes,
        health_score=report.health_score,
        created_by_id=report.created_by_id,
        created_at=report.created_at,
        submitted_at=report.submitted_at,
        approved_at=report.approved_at,
        progresses=[DeliveryProgressPublic.model_validate(p, from_attributes=True) for p in progresses],
        risks=[RiskPublic.model_validate(r, from_attributes=True) for r in risks],
        action_plans=[ActionPlanPublic.model_validate(a, from_attributes=True) for a in action_plans],
        pending_items=[PendingItemPublic.model_validate(p, from_attributes=True) for p in pending_items],
    )


@router.post("/reports", response_model=ReportPublic, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate,
    user: User = Depends(require_any_role(Role.GP)),
    db: AsyncSession = Depends(get_db),
) -> ReportPublic:
    if payload.period_start > payload.period_end:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "period_start não pode ser depois de period_end"
        )
    await _ensure_project_owned(payload.project_id, user, db)
    report = Report(
        project_id=payload.project_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        status=ReportStatus.DRAFT,
        created_by_id=user.id,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return await _serialize_report(report, db)


@router.get("/reports/{report_id}", response_model=ReportPublic)
async def get_report(
    report_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP, Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> ReportPublic:
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report não encontrado")
    await _ensure_project_owned(report.project_id, user, db)
    return await _serialize_report(report, db)


@router.patch("/reports/{report_id}", response_model=ReportPublic)
async def patch_report(
    report_id: uuid.UUID,
    payload: ReportPatch,
    user: User = Depends(require_any_role(Role.GP)),
    db: AsyncSession = Depends(get_db),
) -> ReportPublic:
    """Autosave do wizard. Substitui as listas (progresses, risks, ...) inteiras
    quando passadas — facilita raciocínio do front sem dance de IDs."""
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report não encontrado")
    await _ensure_project_owned(report.project_id, user, db)

    if report.status not in (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"report em {report.status.value} não aceita autosave",
        )

    data = payload.model_dump(exclude_unset=True)
    for key in ("period_start", "period_end", "rag_status", "highlights", "next_steps", "notes"):
        if key in data:
            setattr(report, key, data[key])

    if "progresses" in data:
        await db.execute(delete(DeliveryProgress).where(DeliveryProgress.report_id == report.id))
        for p in data["progresses"] or []:
            db.add(DeliveryProgress(report_id=report.id, **p))
    if "risks" in data:
        await db.execute(delete(Risk).where(Risk.report_id == report.id))
        for r in data["risks"] or []:
            db.add(Risk(report_id=report.id, **r))
    if "action_plans" in data:
        await db.execute(delete(ActionPlan).where(ActionPlan.report_id == report.id))
        for a in data["action_plans"] or []:
            db.add(ActionPlan(report_id=report.id, **a))
    if "pending_items" in data:
        await db.execute(delete(PendingItem).where(PendingItem.report_id == report.id))
        for p in data["pending_items"] or []:
            db.add(PendingItem(report_id=report.id, **p))

    await db.commit()
    await db.refresh(report)
    return await _serialize_report(report, db)


@router.post("/reports/{report_id}/submit", response_model=ReportPublic)
async def submit_report(
    report_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP)),
    db: AsyncSession = Depends(get_db),
) -> ReportPublic:
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report não encontrado")
    await _ensure_project_owned(report.project_id, user, db)
    if report.status not in (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"report em {report.status.value} não pode ser submetido",
        )
    if report.rag_status is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "RAG status é obrigatório para submeter",
        )
    report.status = ReportStatus.SUBMITTED
    report.submitted_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(report)
    return await _serialize_report(report, db)


@router.get("/projects/{project_id}/reports", response_model=list[ReportSummary])
async def list_project_reports(
    project_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP, Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> list[Report]:
    await _ensure_project_owned(project_id, user, db)
    rows = (
        await db.execute(
            select(Report)
            .where(Report.project_id == project_id)
            .order_by(Report.period_end.desc(), Report.created_at.desc())
        )
    ).scalars().all()
    return list(rows)
