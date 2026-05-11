"""Aprovação em 3 estágios + leitura de IAInsights (spec v3.1 §10.1).

Estados:
  draft → submitted (GP submete)
  submitted → pmo_approved | needs_revision (PMO decide)
  pmo_approved → client_released | needs_revision (Cliente decide)

Decisões possíveis (PMO ou Cliente):
  - `approved`              : libera para próximo estágio. Comentário opcional.
  - `approved_with_comment` : libera, mas anexa nota INTERNA (não vai ao cliente).
                              Comentário obrigatório (não vazio).
  - `requested_changes`     : devolve para revisão. Comentário obrigatório.

Cada decisão grava um ReportApproval. Notifica via SSE/in-app/email.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import (
    AIInsight,
    ApprovalDecision,
    ApprovalStage,
    Project,
    Report,
    ReportApproval,
    ReportStatus,
    Role,
    User,
)
from app.schemas.approval import (
    AIInsightPublic,
    ApprovalDecisionPayload,
    ApprovalPublic,
)

router = APIRouter(tags=["approvals"])


def _next_status(stage: ApprovalStage, decision: ApprovalDecision) -> ReportStatus:
    # APPROVED e APPROVED_WITH_COMMENT seguem para o próximo estágio.
    # O comment de APPROVED_WITH_COMMENT é interno (GP+PMO no histórico),
    # nunca vai ao Portal do Cliente — `ClientReportPublic` não expõe approvals.
    if decision in (ApprovalDecision.APPROVED, ApprovalDecision.APPROVED_WITH_COMMENT):
        return (
            ReportStatus.PMO_APPROVED if stage == ApprovalStage.PMO else ReportStatus.CLIENT_RELEASED
        )
    return ReportStatus.NEEDS_REVISION


@router.post("/reports/{report_id}/decide", response_model=ApprovalPublic)
async def decide_report(
    report_id: uuid.UUID,
    payload: ApprovalDecisionPayload,
    user: User = Depends(require_any_role(Role.PMO, Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> ApprovalPublic:
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report não encontrado")
    project = await db.get(Project, report.project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")

    # Define estágio com base no estado atual + role
    if report.status == ReportStatus.SUBMITTED:
        if user.role != Role.PMO:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "apenas PMO pode aprovar este estágio")
        stage = ApprovalStage.PMO
    elif report.status == ReportStatus.PMO_APPROVED:
        if user.role != Role.CLIENT:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "apenas Cliente pode aprovar este estágio"
            )
        if project.client_user_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "cliente não pertence a este projeto")
        stage = ApprovalStage.CLIENT
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"report em {report.status.value} não aceita decisão",
        )

    # Comentário obrigatório quando pede mudança ou aprova com nota interna.
    if payload.decision in (
        ApprovalDecision.REQUESTED_CHANGES,
        ApprovalDecision.APPROVED_WITH_COMMENT,
    ):
        if not payload.comment or not payload.comment.strip():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "comentário obrigatório para requested_changes/approved_with_comment",
            )

    new_status = _next_status(stage, payload.decision)
    report.status = new_status
    if new_status == ReportStatus.PMO_APPROVED:
        report.approved_at = datetime.now(UTC)

    approval = ReportApproval(
        report_id=report.id,
        approver_id=user.id,
        stage=stage,
        decision=payload.decision,
        comment=payload.comment,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)

    # Notificações in-app (best-effort; falha de notif não desfaz aprovação)
    try:
        from app.services.notifications import notify_approval_decision

        await notify_approval_decision(db, report=report, approval=approval, project=project)
    except Exception:  # noqa: BLE001
        pass

    return ApprovalPublic.model_validate(approval, from_attributes=True)


@router.get(
    "/reports/{report_id}/approvals",
    response_model=list[ApprovalPublic],
)
async def list_report_approvals(
    report_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.PMO, Role.GP, Role.CLIENT, Role.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> list[ReportApproval]:
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report não encontrado")
    project = await db.get(Project, report.project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    # GP só vê do próprio; CLIENT só do próprio
    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")
    if user.role == Role.CLIENT and project.client_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cliente não pertence a esse projeto")

    rows = (
        await db.execute(
            select(ReportApproval)
            .where(ReportApproval.report_id == report_id)
            .order_by(ReportApproval.decided_at)
        )
    ).scalars().all()
    return list(rows)


@router.get(
    "/reports/{report_id}/insights",
    response_model=list[AIInsightPublic],
)
async def list_report_insights(
    report_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP, Role.PMO, Role.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> list[AIInsight]:
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report não encontrado")
    project = await db.get(Project, report.project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")

    rows = (
        await db.execute(
            select(AIInsight)
            .where(AIInsight.report_id == report_id)
            .order_by(AIInsight.created_at.desc())
        )
    ).scalars().all()
    return list(rows)
