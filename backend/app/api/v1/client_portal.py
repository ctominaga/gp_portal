"""Portal do Cliente: visão executiva curada + confirmar leitura."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import (
    Baseline,
    BaselineStatus,
    PendingItem,
    PendingItemStatus,
    Project,
    Report,
    ReportApproval,
    ReportStatus,
    Risk,
    RiskStatus,
    Role,
    User,
)
from app.schemas.client import (
    ClientPendingItem,
    ClientProjectView,
    ClientReportPublic,
)
from app.services import health_score

router = APIRouter(prefix="/client", tags=["client"])


async def _ensure_client_owns(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    if user.role != Role.CLIENT or project.client_user_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "cliente não pertence a esse projeto"
        )
    return project


@router.get("/projects", response_model=list[ClientProjectView])
async def list_my_projects(
    user: User = Depends(require_any_role(Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> list[ClientProjectView]:
    rows = (
        await db.execute(
            select(Project).where(Project.client_user_id == user.id)
        )
    ).scalars().all()
    out: list[ClientProjectView] = []
    for p in rows:
        out.append(await _build_view(p, db))
    return out


@router.get("/projects/{project_id}", response_model=ClientProjectView)
async def get_my_project(
    project_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> ClientProjectView:
    project = await _ensure_client_owns(project_id, user, db)
    return await _build_view(project, db)


@router.post("/reports/{report_id}/confirm-read")
async def confirm_read(
    report_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cliente confirma que leu o report. Cria um ReportApproval do tipo CLIENT/approved."""
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report não encontrado")
    project = await _ensure_client_owns(report.project_id, user, db)
    if report.status not in (ReportStatus.PMO_APPROVED, ReportStatus.CLIENT_RELEASED):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "só é possível confirmar leitura de reports aprovados pelo PMO",
        )
    db.add(
        ReportApproval(
            report_id=report.id,
            approver_id=user.id,
            stage=__import__("app.models", fromlist=["ApprovalStage"]).ApprovalStage.CLIENT,
            decision=__import__("app.models", fromlist=["ApprovalDecision"]).ApprovalDecision.APPROVED,
            comment="Confirmação de leitura.",
        )
    )
    if report.status == ReportStatus.PMO_APPROVED:
        report.status = ReportStatus.CLIENT_RELEASED
        report.approved_at = datetime.now(UTC)
    await db.commit()
    return {"ack": "ok", "project_id": str(project.id)}


# ---------- helpers ----------


async def _build_view(project: Project, db: AsyncSession) -> ClientProjectView:
    breakdown = await health_score.compute_for_project(db, project.id)

    # Apenas reports liberados ao cliente
    reports = list(
        (
            await db.execute(
                select(Report)
                .where(
                    Report.project_id == project.id,
                    Report.status.in_([
                        ReportStatus.PMO_APPROVED,
                        ReportStatus.CLIENT_RELEASED,
                        ReportStatus.ARCHIVED,
                    ]),
                )
                .order_by(Report.period_end.desc())
            )
        ).scalars().all()
    )

    public_reports: list[ClientReportPublic] = []
    open_pending_total = 0
    open_risks_total = 0
    latest_rag = None
    for r in reports:
        pending = list(
            (
                await db.execute(
                    select(PendingItem).where(
                        PendingItem.report_id == r.id,
                        PendingItem.status == PendingItemStatus.OPEN,
                        PendingItem.owner_party == "client",
                    )
                )
            ).scalars().all()
        )
        if r.id == reports[0].id:
            latest_rag = r.rag_status
            risks = list(
                (
                    await db.execute(
                        select(Risk).where(
                            Risk.report_id == r.id,
                            Risk.status == RiskStatus.OPEN,
                        )
                    )
                ).scalars().all()
            )
            open_risks_total = len(risks)
            open_pending_total = len(pending)
        public_reports.append(
            ClientReportPublic(
                id=r.id,
                period_start=r.period_start,
                period_end=r.period_end,
                rag_status=r.rag_status,
                status=r.status,
                highlights=r.highlights,
                next_steps=r.next_steps,
                submitted_at=r.submitted_at,
                approved_at=r.approved_at,
                pending_items=[
                    ClientPendingItem(
                        description=p.description,
                        due_date=p.due_date,
                        owner_party=p.owner_party,
                    )
                    for p in pending
                ],
            )
        )

    return ClientProjectView(
        id=project.id,
        name=project.name,
        client_name=project.client_name,
        status=project.status.value,
        started_at=project.started_at,
        latest_rag=latest_rag,
        health_score=breakdown.score,
        open_pending_items=open_pending_total,
        open_risks_count=open_risks_total,
        reports=public_reports,
    )


# ---------- diff de propostas / baselines ----------


async def compute_baseline_diff(
    db: AsyncSession,
    *,
    base_baseline: Baseline,
    new_baseline: Baseline,
) -> dict:
    """Read-only: compara dois baselines do MESMO projeto e devolve added/removed/changed.

    Não cria ScopeChange. Use `diff_baselines` para criar ScopeChange (chamado
    pelo worker quando uma nova baseline é gerada).
    """
    from app.models import Deliverable

    rows_old = list(
        (
            await db.execute(
                select(Deliverable).where(Deliverable.baseline_id == base_baseline.id)
            )
        ).scalars().all()
    )
    rows_new = list(
        (
            await db.execute(
                select(Deliverable).where(Deliverable.baseline_id == new_baseline.id)
            )
        ).scalars().all()
    )

    by_code_old = {d.code: d for d in rows_old if d.code}
    by_code_new = {d.code: d for d in rows_new if d.code}

    added = []
    removed = []
    changed = []

    for code, d_new in by_code_new.items():
        if code not in by_code_old:
            added.append({
                "kind": "added",
                "code": code,
                "title_old": None,
                "title_new": d_new.title,
                "phase_old": None,
                "phase_new": d_new.phase,
                "complexity_old": None,
                "complexity_new": d_new.complexity.value if d_new.complexity else None,
            })
        else:
            d_old = by_code_old[code]
            if (
                d_old.title != d_new.title
                or d_old.phase != d_new.phase
                or d_old.complexity != d_new.complexity
            ):
                changed.append({
                    "kind": "changed",
                    "code": code,
                    "title_old": d_old.title,
                    "title_new": d_new.title,
                    "phase_old": d_old.phase,
                    "phase_new": d_new.phase,
                    "complexity_old": d_old.complexity.value if d_old.complexity else None,
                    "complexity_new": d_new.complexity.value if d_new.complexity else None,
                })

    for code, d_old in by_code_old.items():
        if code not in by_code_new:
            removed.append({
                "kind": "removed",
                "code": code,
                "title_old": d_old.title,
                "title_new": None,
                "phase_old": d_old.phase,
                "phase_new": None,
                "complexity_old": d_old.complexity.value if d_old.complexity else None,
                "complexity_new": None,
            })

    return {
        "base_baseline_id": str(base_baseline.id),
        "new_baseline_id": str(new_baseline.id),
        "added": added,
        "removed": removed,
        "changed": changed,
    }


async def diff_baselines(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    base_baseline: Baseline,
    new_baseline: Baseline,
) -> dict:
    """Compara dois baselines e cria um ScopeChange por added/removed.

    Idempotente: só cria ScopeChange para itens que ainda não têm registro
    correspondente para `new_baseline.id`. Chamado pelo worker quando uma v2+
    é gerada e (com idempotência garantida) pode ser chamado por endpoints.
    """
    from app.models import ScopeChange

    diff = await compute_baseline_diff(
        db, base_baseline=base_baseline, new_baseline=new_baseline
    )
    existing_descriptions: set[str] = set(
        (
            await db.execute(
                select(ScopeChange.description).where(
                    ScopeChange.impact_baseline_id == new_baseline.id
                )
            )
        ).scalars().all()
    )

    scope_changes_created = 0
    for entry in diff["added"]:
        desc = f"Adicionado: {entry['code']} · {entry['title_new']}"
        if desc in existing_descriptions:
            continue
        db.add(
            ScopeChange(
                project_id=project_id,
                description=desc,
                impact_baseline_id=new_baseline.id,
            )
        )
        scope_changes_created += 1
    for entry in diff["removed"]:
        desc = f"Removido: {entry['code']} · {entry['title_old']}"
        if desc in existing_descriptions:
            continue
        db.add(
            ScopeChange(
                project_id=project_id,
                description=desc,
                impact_baseline_id=new_baseline.id,
            )
        )
        scope_changes_created += 1

    if scope_changes_created:
        await db.commit()
    return {**diff, "scope_changes_created": scope_changes_created}


@router.get("/diff/{base_baseline_id}/{new_baseline_id}")
async def baseline_diff(
    base_baseline_id: uuid.UUID,
    new_baseline_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP, Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Endpoint público (GP|PMO) para comparar dois baselines.

    Usado pela tela de diff de propostas v1 vs v2.
    """
    base = await db.get(Baseline, base_baseline_id)
    new_b = await db.get(Baseline, new_baseline_id)
    if not base or not new_b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "baseline não encontrado")
    if base.project_id != new_b.project_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "baselines de projetos diferentes"
        )
    project = await db.get(Project, base.project_id)
    if user.role == Role.GP and project and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")
    return await compute_baseline_diff(db, base_baseline=base, new_baseline=new_b)


__all__ = ["router", "diff_baselines", "compute_baseline_diff"]


# Garantir que BaselineStatus é importável (usado por _build_view)
_ = BaselineStatus
