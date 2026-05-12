"""Endpoints do portfólio PMO: dashboard com Health Score + config de pesos.

Health Score segue spec v3.1 §10.3 — 5 componentes ponderados.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import (
    OPEN_RISK_STATUSES,
    PendingItem,
    PendingItemStatus,
    Project,
    Report,
    Risk,
    RiskLevel,
    Role,
    ScopeChange,
    ScopeChangeStatus,
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


def _components_from_breakdown(
    b: health_score.HealthScoreBreakdown,
) -> HealthScoreComponents:
    return HealthScoreComponents(
        rag_avg=b.rag_avg,
        spi=b.spi,
        risk_inverse=b.risk_inverse,
        resolution_rate=b.resolution_rate,
        stability=b.stability,
    )


@router.get("", response_model=PortfolioOverview)
async def portfolio_overview(
    _user: User = Depends(require_any_role(Role.PMO, Role.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> PortfolioOverview:
    cfg = await health_score.get_config(db)

    rows = (
        await db.execute(
            select(Project, User.name)
            .join(User, User.id == Project.gp_user_id, isouter=True)
        )
    ).all()

    # F5.2 — count de ScopeChanges PROPOSED agregado por projeto (1 query
    # única em vez de N). Alimenta o badge "N transições pendentes" no card.
    pending_by_project: dict[uuid.UUID, int] = dict(
        (
            await db.execute(
                select(ScopeChange.project_id, func.count(ScopeChange.id))
                .where(ScopeChange.status == ScopeChangeStatus.PROPOSED)
                .group_by(ScopeChange.project_id)
            )
        ).all()
    )

    cards: list[PortfolioProjectCard] = []
    for project, gp_name in rows:
        breakdown = await health_score.compute_for_project(db, project.id, cfg=cfg)
        h = HealthScorePublic(
            project_id=project.id,
            score=breakdown.score,
            band=breakdown.band,
            components=_components_from_breakdown(breakdown),
            weights_applied=breakdown.weights_applied,
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
            # OPEN_RISK_STATUSES = IDENTIFIED+MONITORING (MATERIALIZED conta noutro lugar)
            open_risk_rows = list(
                (
                    await db.execute(
                        select(Risk).where(
                            Risk.report_id == breakdown.last_report_id,
                            Risk.status.in_(OPEN_RISK_STATUSES),
                        )
                    )
                ).scalars().all()
            )
            open_risks = len(open_risk_rows)
            # `level` é property derivada — filtra em Python (volume baixo no piloto).
            open_critical = sum(
                1 for r in open_risk_rows if r.level == RiskLevel.CRITICAL
            )
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
                pending_transitions_count=int(pending_by_project.get(project.id, 0)),
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
    weights = payload.health_score_weights.model_dump()
    cfg = await health_score.update_weights(
        db, weights=weights, updated_by_id=user.id
    )
    return PortfolioConfigPublic.model_validate(cfg, from_attributes=True)


# Alias PATCH conforme spec v3.1 §10.3 — semanticamente um update parcial,
# mas a Pydantic já valida o body completo (HealthScoreWeights requer os 5 pesos).
@router.patch("/config", response_model=PortfolioConfigPublic)
async def patch_portfolio_config(
    payload: PortfolioConfigUpdate,
    user: User = Depends(require_any_role(Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> PortfolioConfigPublic:
    weights = payload.health_score_weights.model_dump()
    cfg = await health_score.update_weights(
        db, weights=weights, updated_by_id=user.id
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
        components=_components_from_breakdown(breakdown),
        weights_applied=breakdown.weights_applied,
        last_report_id=breakdown.last_report_id,
        last_report_period_end=breakdown.last_report_period_end,
    )
