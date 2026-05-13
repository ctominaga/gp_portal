"""F5.4 — Modo de Report Assistido por IA (spec v3.1 §10.2).

`prepopulate_report` cria um Report DRAFT já populado com:
  - Risks herdados do report anterior com status IDENTIFIED ou MONITORING
    (constante `OPEN_RISK_STATUSES`, definida em F5.1 — não inventar filtro).
  - PendingItems herdados com status OPEN.
  - DeliveryProgress placeholders para Deliverables do baseline ACTIVE cuja
    `due_date` cai na janela `[period_start - 30 days, period_end]`. A margem
    para trás captura entregas em atraso recentes — trabalho real do período.

Todos os filhos herdados recebem `is_prepopulated=True`. O backend zera essa
flag no PATCH quando detecta edição (implementação em F5.4 commit 3).

Limites de escopo (decisões F5.4):
  - ActionPlan **não** herda (decisão Q5 = b). GP vinculará manualmente se
    o Risk herdado ainda merecer ação. Botão "Criar plano de ação vinculado"
    no wizard fica como débito F5.4.Y se sair do escopo do commit 3.
  - Sugestões textuais da IA ("Ainda está ativo?") **não** entram no MVP
    (decisão Q3 = c). Débito F5.4.X — depende de agente real (F2.6).
  - RAG e textos (highlights/next_steps/notes) **não** herdam. GP avalia
    a cada período.

Idempotência: chamar 2x com mesmo `(project_id, period_start, period_end)`
levanta `PrepopulateConflict`. O endpoint traduz para 409.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OPEN_RISK_STATUSES,
    Baseline,
    BaselineStatus,
    Deliverable,
    DeliveryProgress,
    PendingItem,
    PendingItemStatus,
    ProgressStatus,
    Project,
    Report,
    ReportStatus,
    Risk,
)


# Janela para incluir Deliverables com prazo "no período" (briefing C de F5.4).
# Captura entregas levemente atrasadas que continuam sendo trabalho real do
# novo período. Confirma com Christopher se 30 dias é janela adequada — pode
# virar configurável em F5.X se necessário.
_OVERDUE_WINDOW_DAYS = 30

# Reports que servem como "anterior" para herança. DRAFT é descartado
# (drafts abandonados não são fonte confiável); NEEDS_REVISION também
# (ainda em revisão, estado intermediário). Status terminais ou aguardando
# decisão externa contam.
_HERITABLE_REPORT_STATUSES: tuple[ReportStatus, ...] = (
    ReportStatus.SUBMITTED,
    ReportStatus.PMO_APPROVED,
    ReportStatus.CLIENT_RELEASED,
    ReportStatus.ARCHIVED,
)


class PrepopulateError(ValueError):
    """Erro de negócio do prepopulate — endpoint traduz para HTTPException."""

    def __init__(self, message: str, *, http_status: int):
        super().__init__(message)
        self.http_status = http_status


class PrepopulateConflict(PrepopulateError):
    """409 — report já existe no período OU projeto sem baseline ativo."""

    def __init__(self, message: str):
        super().__init__(message, http_status=409)


async def _find_existing_in_period(
    db: AsyncSession, *, project_id: uuid.UUID, period_start: date, period_end: date
) -> Report | None:
    """Idempotência: já existe report no mesmo período (qualquer status)?"""
    return (
        await db.execute(
            select(Report).where(
                Report.project_id == project_id,
                Report.period_start == period_start,
                Report.period_end == period_end,
            )
        )
    ).scalar_one_or_none()


async def _find_active_baseline(
    db: AsyncSession, *, project_id: uuid.UUID
) -> Baseline | None:
    return (
        await db.execute(
            select(Baseline).where(
                Baseline.project_id == project_id,
                Baseline.status == BaselineStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()


async def _find_previous_report(
    db: AsyncSession, *, project_id: uuid.UUID
) -> Report | None:
    """Último report herdável do projeto (status terminal ou aguardando externa)."""
    return (
        await db.execute(
            select(Report)
            .where(
                Report.project_id == project_id,
                Report.status.in_(_HERITABLE_REPORT_STATUSES),
            )
            .order_by(Report.period_end.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _deliverables_in_window(
    db: AsyncSession,
    *,
    baseline_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> list[Deliverable]:
    """Deliverables do baseline com due_date em [start - 30d, end].

    Margem para trás captura entregas atrasadas que continuam sendo trabalho
    real do novo período (briefing C de F5.4).
    """
    window_start = period_start - timedelta(days=_OVERDUE_WINDOW_DAYS)
    rows = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.baseline_id == baseline_id,
                Deliverable.due_date.is_not(None),
                and_(
                    Deliverable.due_date >= window_start,
                    Deliverable.due_date <= period_end,
                ),
            )
        )
    ).scalars().all()
    return list(rows)


async def prepopulate_report(
    db: AsyncSession,
    *,
    project: Project,
    period_start: date,
    period_end: date,
    creator_user_id: uuid.UUID,
) -> Report:
    """Cria Report DRAFT já populado com herança do report anterior.

    Validações (cascata; primeira falha vence):
      1. Idempotência: report existente no mesmo período → 409 com link
      2. Baseline ativo: projeto sem baseline ACTIVE → 409 (briefing E)
      3. period_start <= period_end (validado em camada Pydantic; defensivo aqui)

    Retorna o `Report` recém-criado (sem refresh dos filhos — caller faz
    `_serialize_report` ou similar para hidratar).
    """
    if period_start > period_end:
        raise PrepopulateError(
            "period_start não pode ser depois de period_end", http_status=400
        )

    existing = await _find_existing_in_period(
        db, project_id=project.id, period_start=period_start, period_end=period_end
    )
    if existing:
        raise PrepopulateConflict(
            f"Já existe report no período {period_start.isoformat()}–"
            f"{period_end.isoformat()}. Acesse-o em /reports/{existing.id}."
        )

    baseline = await _find_active_baseline(db, project_id=project.id)
    if not baseline:
        raise PrepopulateConflict(
            "Projeto sem baseline ativo — ative um baseline antes de criar reports."
        )

    # 1) Cria o Report DRAFT base.
    report = Report(
        project_id=project.id,
        period_start=period_start,
        period_end=period_end,
        status=ReportStatus.DRAFT,
        created_by_id=creator_user_id,
    )
    db.add(report)
    await db.flush()  # garante report.id para os filhos abaixo

    # 2) Herança do report anterior (Risks + PendingItems).
    previous = await _find_previous_report(db, project_id=project.id)
    if previous:
        # Risks abertos (OPEN_RISK_STATUSES = IDENTIFIED + MONITORING).
        # MATERIALIZED e MITIGATED ficam para trás — viraram problema (vão pra
        # retrospectiva no encerramento) ou foram resolvidos.
        prev_open_risks = list(
            (
                await db.execute(
                    select(Risk).where(
                        Risk.report_id == previous.id,
                        Risk.status.in_(OPEN_RISK_STATUSES),
                    )
                )
            ).scalars().all()
        )
        for r in prev_open_risks:
            db.add(
                Risk(
                    report_id=report.id,
                    description=r.description,
                    probability=r.probability,
                    impact=r.impact,
                    mitigation_plan=r.mitigation_plan,
                    owner_id=r.owner_id,
                    due_date=r.due_date,
                    status=r.status,
                    is_prepopulated=True,
                )
            )

        # PendingItems OPEN (briefing D — preserva owner_party original).
        prev_open_pending = list(
            (
                await db.execute(
                    select(PendingItem).where(
                        PendingItem.report_id == previous.id,
                        PendingItem.status == PendingItemStatus.OPEN,
                    )
                )
            ).scalars().all()
        )
        for p in prev_open_pending:
            db.add(
                PendingItem(
                    report_id=report.id,
                    description=p.description,
                    owner_party=p.owner_party,
                    due_date=p.due_date,
                    status=p.status,
                    impact=p.impact,
                    is_prepopulated=True,
                )
            )

    # 3) DeliveryProgress placeholders (independem de previous report — vêm do
    # baseline ACTIVE no momento da criação).
    deliv_window = await _deliverables_in_window(
        db, baseline_id=baseline.id,
        period_start=period_start, period_end=period_end,
    )
    for d in deliv_window:
        db.add(
            DeliveryProgress(
                report_id=report.id,
                deliverable_id=d.id,
                status=ProgressStatus.PLANNED,
                percent_complete=0,
                comment=None,
                revised_date=None,
                acceptance_confirmed=None,
                deviation_flag=False,
                is_prepopulated=True,
            )
        )

    await db.commit()
    await db.refresh(report)
    return report
