"""Endpoints do portfólio PMO: dashboard com Health Score + config de pesos."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import (
    PendingItem,
    PendingItemStatus,
    Project,
    Report,
    Risk,
    RiskStatus,
    Role,
    User,
)
from app.schemas.portfolio import (
    HealthScoreComponents,
    HealthScorePublic,
    PortfolioConfigPublic,
    PortfolioConfigUpdate,
    PortfolioOverview,
    PortfolioProjectCard,
)
from app.services import health_score

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioOverview)
async def portfolio_overview(
    _user: User = Depends(require_any_role(Role.PMO, Role.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> PortfolioOverview:
    cfg = await health_score.get_config(db)

    # Carrega todos os projetos + nome do GP em uma query
    rows = (
        await db.execute(
            select(Project, User.name)
            .join(User, User.id == Project.gp_user_id, isouter=True)
        )
    ).all()

    cards: list[PortfolioProjectCard] = []
    for project, gp_name in rows:
        breakdown = await health_score.compute_for_project(db, project.id, cfg=cfg)
        components = HealthScoreComponents(
            progress=breakdown.progress,
            risks=breakdown.risks,
            pendings=breakdown.pendings,
            schedule=breakdown.schedule,
        )
        h = HealthScorePublic(
            project_id=project.id,
            score=breakdown.score,
            band=breakdown.band,
            components=components,
            last_report_id=breakdown.last_report_id,
            last_report_period_end=breakdown.last_report_period_end,
        )

        # Contadores no último report submitted
        last_rag = None
        open_risks = 0
        open_critical = 0
        pending_client = 0
        if breakdown.last_report_id:
            last_report = await db.get(Report, breakdown.last_report_id)
            if last_report:
                last_rag = last_report.rag_status
            open_risks = len(
                list(
                    (
                        await db.execute(
                            select(Risk).where(
                                Risk.report_id == breakdown.last_report_id,
                                Risk.status == RiskStatus.OPEN,
                            )
                        )
                    ).scalars().all()
                )
            )
            open_critical = (
                await db.execute(
                    select(func.count())
                    .select_from(Risk)
                    .where(
                        Risk.report_id == breakdown.last_report_id,
                        Risk.severity == "critical",
                        Risk.status == RiskStatus.OPEN,
                    )
                )
            ).scalar_one()
            pending_client = (
                await db.execute(
                    select(func.count())
                    .select_from(PendingItem)
                    .where(
                        PendingItem.report_id == breakdown.last_report_id,
                        PendingItem.status == PendingItemStatus.OPEN,
                        PendingItem.owner_party == "client",
                    )
                )
            ).scalar_one()

        cards.append(
            PortfolioProjectCard(
                project_id=project.id,
                project_name=project.name,
                client_name=project.client_name,
                gp_user_id=project.gp_user_id,
                gp_name=gp_name,
                health=h,
                last_report_rag=last_rag,
                open_risks_count=open_risks,
                open_critical_alerts=int(open_critical or 0),
                pending_client_items=int(pending_client or 0),
            )
        )

    avg = (
        sum(c.health.score for c in cards) / len(cards) if cards else None
    )
    counts: dict[str, int] = {"green": 0, "amber": 0, "red": 0}
    for c in cards:
        counts[c.health.band] += 1

    return PortfolioOverview(
        projects=cards,
        total_projects=len(cards),
        avg_health_score=round(avg, 1) if avg is not None else None,
        counts_by_band=counts,
    )


@router.get("/config", response_model=PortfolioConfigPublic)
async def get_portfolio_config(
    _user: User = Depends(require_any_role(Role.PMO, Role.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> PortfolioConfigPublic:
    cfg = await health_score.get_config(db)
    return PortfolioConfigPublic.model_validate(cfg, from_attributes=True)


@router.put("/config", response_model=PortfolioConfigPublic)
async def update_portfolio_config(
    payload: PortfolioConfigUpdate,
    user: User = Depends(require_any_role(Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> PortfolioConfigPublic:
    total = (
        payload.weight_progress
        + payload.weight_risks
        + payload.weight_pendings
        + payload.weight_schedule
    )
    if total <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "soma dos pesos deve ser > 0")
    cfg = await health_score.update_config(
        db,
        weight_progress=payload.weight_progress,
        weight_risks=payload.weight_risks,
        weight_pendings=payload.weight_pendings,
        weight_schedule=payload.weight_schedule,
        updated_by_id=user.id,
    )
    return PortfolioConfigPublic.model_validate(cfg, from_attributes=True)


@router.get("/projects/{project_id}/health", response_model=HealthScorePublic)
async def project_health(
    project_id: uuid.UUID,
    _user: User = Depends(require_any_role(Role.PMO, Role.OPERATOR, Role.GP)),
    db: AsyncSession = Depends(get_db),
) -> HealthScorePublic:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    breakdown = await health_score.compute_for_project(db, project_id)
    return HealthScorePublic(
        project_id=breakdown.project_id,
        score=breakdown.score,
        band=breakdown.band,
        components=HealthScoreComponents(
            progress=breakdown.progress,
            risks=breakdown.risks,
            pendings=breakdown.pendings,
            schedule=breakdown.schedule,
        ),
        last_report_id=breakdown.last_report_id,
        last_report_period_end=breakdown.last_report_period_end,
    )
