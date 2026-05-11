"""Endpoints de Report — CRUD + PATCH idempotente para autosave do wizard."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import (
    ActionPlan,
    Deliverable,
    DeliveryProgress,
    PendingItem,
    ProgressStatus,
    Project,
    RAGStatus,
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

# Worst-of-3 dos status RAG. Se alguma dimensão é None, o agregado também é None.
_RAG_RANK = {RAGStatus.GREEN: 0, RAGStatus.AMBER: 1, RAGStatus.RED: 2}


def _aggregate_rag(*dims: RAGStatus | None) -> RAGStatus | None:
    """Worst-of-3. Retorna None se qualquer dimensão for None (não preencheu)."""
    values = [d for d in dims if d is not None]
    if not values or len(values) != len(dims):
        return None
    return max(values, key=lambda v: _RAG_RANK[v])

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

    # Expand de vínculos (spec v3.1 §4.2.4) — busca descrições em lote para
    # evitar N+1 nas próximas linhas. Vazio se nenhum plano tem vínculo.
    linked_risk_ids = {a.linked_risk_id for a in action_plans if a.linked_risk_id}
    linked_deliv_ids = {a.linked_deliverable_id for a in action_plans if a.linked_deliverable_id}
    risk_desc_by_id: dict[uuid.UUID, str] = {}
    deliv_title_by_id: dict[uuid.UUID, str] = {}
    if linked_risk_ids:
        rows = (
            await db.execute(
                select(Risk.id, Risk.description).where(Risk.id.in_(linked_risk_ids))
            )
        ).all()
        risk_desc_by_id = {r[0]: r[1] for r in rows}
    if linked_deliv_ids:
        rows = (
            await db.execute(
                select(Deliverable.id, Deliverable.title).where(
                    Deliverable.id.in_(linked_deliv_ids)
                )
            )
        ).all()
        deliv_title_by_id = {r[0]: r[1] for r in rows}

    def _serialize_action_plan(a: ActionPlan) -> ActionPlanPublic:
        obj = ActionPlanPublic.model_validate(a, from_attributes=True)
        if a.linked_risk_id and a.linked_risk_id in risk_desc_by_id:
            obj.linked_risk_description = risk_desc_by_id[a.linked_risk_id]
        if a.linked_deliverable_id and a.linked_deliverable_id in deliv_title_by_id:
            obj.linked_deliverable_title = deliv_title_by_id[a.linked_deliverable_id]
        return obj

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
        rag_prazo=report.rag_prazo,
        rag_escopo=report.rag_escopo,
        rag_qualidade=report.rag_qualidade,
        rag_prazo_justificativa=report.rag_prazo_justificativa,
        rag_escopo_justificativa=report.rag_escopo_justificativa,
        rag_qualidade_justificativa=report.rag_qualidade_justificativa,
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
        action_plans=[_serialize_action_plan(a) for a in action_plans],
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
    scalar_keys = (
        "period_start", "period_end",
        "rag_status",
        "rag_prazo", "rag_escopo", "rag_qualidade",
        "rag_prazo_justificativa", "rag_escopo_justificativa", "rag_qualidade_justificativa",
        "highlights", "next_steps", "notes",
    )
    for key in scalar_keys:
        if key in data:
            setattr(report, key, data[key])

    # Mantém rag_status agregado em sincronia se as 3 dimensões estiverem preenchidas.
    if any(k in data for k in ("rag_prazo", "rag_escopo", "rag_qualidade")):
        agg = _aggregate_rag(report.rag_prazo, report.rag_escopo, report.rag_qualidade)
        if agg is not None:
            report.rag_status = agg

    if "progresses" in data:
        # spec v3.1 §4.2.2: status=done + percent=100 exige confirmação do
        # critério de aceite (modal "Critério de aceite foi atingido?"). Sem
        # acceptance_confirmed=True, o save é rejeitado.
        for p in data["progresses"] or []:
            is_done_complete = (
                p.get("status") == ProgressStatus.DONE.value
                and p.get("percent_complete") == 100
            )
            if is_done_complete and p.get("acceptance_confirmed") is not True:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "entregável marcado como concluído com 100% exige "
                    "confirmação do critério de aceite "
                    "(acceptance_confirmed=true)",
                )

        # Pré-carrega due_date dos deliverables envolvidos para calcular deviation_flag
        deliv_ids = [p["deliverable_id"] for p in (data["progresses"] or [])]
        due_by_deliv: dict[uuid.UUID, date | None] = {}
        if deliv_ids:
            rows = (
                await db.execute(
                    select(Deliverable.id, Deliverable.due_date).where(Deliverable.id.in_(deliv_ids))
                )
            ).all()
            due_by_deliv = {r[0]: r[1] for r in rows}

        await db.execute(delete(DeliveryProgress).where(DeliveryProgress.report_id == report.id))
        # Cross-model auto-update (spec v3.1 §4.2.2 + §6.4.1): DeliveryProgress
        # com status=done + percent=100 + acceptance_confirmed=True promove
        # Deliverable.status para CONCLUDED. Caso patológico de
        # `acceptance_confirmed=True` em progresso parcial NÃO promove
        # (a regra é a conjunção das 3 condições, não só a flag).
        from app.models import DeliverableStatus as _DStatus

        deliv_ids_to_conclude: set[uuid.UUID] = set()
        for p in data["progresses"] or []:
            revised = p.get("revised_date")
            planned = due_by_deliv.get(p["deliverable_id"])
            deviation = bool(revised and planned and revised != planned)
            db.add(
                DeliveryProgress(
                    report_id=report.id,
                    deviation_flag=deviation,
                    **p,
                )
            )
            if (
                p.get("status") == ProgressStatus.DONE.value
                and p.get("percent_complete") == 100
                and p.get("acceptance_confirmed") is True
            ):
                deliv_ids_to_conclude.add(p["deliverable_id"])
        if deliv_ids_to_conclude:
            await db.execute(
                update(Deliverable)
                .where(Deliverable.id.in_(deliv_ids_to_conclude))
                .values(status=_DStatus.CONCLUDED)
            )
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

    # As 3 dimensões são obrigatórias
    missing_dims = [
        name
        for name, value in (
            ("prazo", report.rag_prazo),
            ("escopo", report.rag_escopo),
            ("qualidade", report.rag_qualidade),
        )
        if value is None
    ]
    if missing_dims:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"RAG por dimensão obrigatório (faltando: {', '.join(missing_dims)})",
        )

    # Justificativa obrigatória para A/R em qualquer dimensão
    rag_with_just = (
        ("prazo", report.rag_prazo, report.rag_prazo_justificativa),
        ("escopo", report.rag_escopo, report.rag_escopo_justificativa),
        ("qualidade", report.rag_qualidade, report.rag_qualidade_justificativa),
    )
    missing_just = [
        name
        for name, dim, just in rag_with_just
        if dim in (RAGStatus.AMBER, RAGStatus.RED) and not (just and just.strip())
    ]
    if missing_just:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"justificativa obrigatória para Amarelo/Vermelho em: {', '.join(missing_just)}",
        )

    # rag_status agregado é derivado pelo backend (worst-of-3)
    report.rag_status = _aggregate_rag(report.rag_prazo, report.rag_escopo, report.rag_qualidade)

    report.status = ReportStatus.SUBMITTED
    report.submitted_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(report)

    # Cacheia Health Score derivado para listagens rápidas
    try:
        from app.services import health_score as _hs

        breakdown = await _hs.compute_for_project(db, report.project_id)
        await _hs.cache_to_report(db, report, breakdown.score)
    except Exception:  # noqa: BLE001
        pass

    # Dispara agente de análise (worker stub; worker real em F2.6)
    try:
        from app.services.report_analyzer_stub import schedule_analysis

        schedule_analysis(report.id)
    except Exception:  # noqa: BLE001
        pass

    # Notifica PMOs
    try:
        from app.services.notifications import notify_report_submitted

        project = await db.get(Project, report.project_id)
        if project:
            await notify_report_submitted(db, report=report, project=project)
    except Exception:  # noqa: BLE001
        pass

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
