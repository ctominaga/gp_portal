"""Empacotamento do export LGPD em ZIP.

Implementa o GET /me/data-export do piloto: monta o ZIP em memória com
os 5 arquivos descritos em docs/lgpd.md §"Portabilidade":

  me.json                       — cadastro próprio do titular
  projects_as_gp.json           — projetos onde gp_user_id == titular,
                                  com TODA a árvore (Baselines + Deliverables,
                                  Reports em qualquer status, filhos do Report,
                                  Approvals, ScopeChanges, AgentRunLog)
  projects_as_client.json       — projetos onde client_user_id == titular,
                                  com filtro de minimização: Reports apenas
                                  em CLIENT_RELEASED/ARCHIVED, Approvals apenas
                                  onde o titular foi o aprovador, SEM
                                  AgentRunLog, SEM Baselines/ScopeChanges
                                  internos
  data_processing_records.json  — histórico LGPD do titular (EXPORT/DELETION/...)
  README.txt                    — explicação humana + carimbo da extração

Decisões de design (ADR F5.7 abertura — Q2/Q5):
  - filtro CLIENT é cirúrgico e implementado AQUI, não no schema. Tudo o que
    sai do `projects_as_client` representa dado já visível ao cliente via
    Portal ou via Approval em que ele atuou. Reports em DRAFT/SUBMITTED/
    PMO_APPROVED/NEEDS_REVISION não vazam.
  - JSON ordenado por chave para diff/auditoria estáveis; UTF-8, sem ASCII
    escape.
"""
from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActionPlan,
    AgentRunLog,
    Baseline,
    DataProcessingRecord,
    Deliverable,
    DeliveryProgress,
    PendingItem,
    Project,
    Report,
    ReportApproval,
    ReportStatus,
    Risk,
    ScopeChange,
    User,
)
from app.schemas.data_export import (
    ActionPlanExport,
    AgentRunLogExport,
    ApprovalExport,
    BaselineExport,
    DataProcessingRecordExport,
    DeliverableExport,
    DeliveryProgressExport,
    PendingItemExport,
    ProjectAsClientExport,
    ProjectAsGpExport,
    ReportExport,
    RiskExport,
    ScopeChangeExport,
    UserExport,
)

# Reports que o cliente JÁ viu (ou que estão arquivados pós-visualização).
# Tudo fora deste conjunto fica de fora do export CLIENT (Q2 da ADR F5.7).
_CLIENT_VISIBLE_REPORT_STATUSES: frozenset[ReportStatus] = frozenset({
    ReportStatus.CLIENT_RELEASED,
    ReportStatus.ARCHIVED,
})


def _dump(model) -> dict:
    """Serializa um modelo Pydantic em modo JSON (UUID→str, datetime→ISO)."""
    return model.model_dump(mode="json")


async def _build_report_export(db: AsyncSession, report: Report) -> ReportExport:
    risks = list(
        (await db.execute(select(Risk).where(Risk.report_id == report.id)))
        .scalars().all()
    )
    pendings = list(
        (await db.execute(select(PendingItem).where(PendingItem.report_id == report.id)))
        .scalars().all()
    )
    actions = list(
        (await db.execute(select(ActionPlan).where(ActionPlan.report_id == report.id)))
        .scalars().all()
    )
    progresses = list(
        (
            await db.execute(
                select(DeliveryProgress).where(DeliveryProgress.report_id == report.id)
            )
        ).scalars().all()
    )
    return ReportExport(
        id=report.id,
        project_id=report.project_id,
        period_start=report.period_start,
        period_end=report.period_end,
        status=report.status.value,
        rag_status=report.rag_status.value if report.rag_status else None,
        rag_prazo=report.rag_prazo.value if report.rag_prazo else None,
        rag_escopo=report.rag_escopo.value if report.rag_escopo else None,
        rag_qualidade=report.rag_qualidade.value if report.rag_qualidade else None,
        highlights=report.highlights,
        next_steps=report.next_steps,
        notes=report.notes,
        health_score=report.health_score,
        created_by_id=report.created_by_id,
        created_at=report.created_at,
        submitted_at=report.submitted_at,
        approved_at=report.approved_at,
        risks=[
            RiskExport(
                id=r.id,
                description=r.description,
                probability=r.probability.value,
                impact=r.impact.value,
                mitigation_plan=r.mitigation_plan,
                owner_id=r.owner_id,
                due_date=r.due_date,
                status=r.status.value,
                created_at=r.created_at,
            )
            for r in risks
        ],
        pending_items=[
            PendingItemExport(
                id=p.id,
                description=p.description,
                owner_party=p.owner_party,
                due_date=p.due_date,
                status=p.status.value,
                impact=p.impact,
                created_at=p.created_at,
            )
            for p in pendings
        ],
        action_plans=[
            ActionPlanExport(
                id=a.id,
                description=a.description,
                objective=a.objective,
                owner_id=a.owner_id,
                due_date=a.due_date,
                status=a.status.value,
                linked_risk_id=a.linked_risk_id,
                linked_deliverable_id=a.linked_deliverable_id,
            )
            for a in actions
        ],
        delivery_progresses=[
            DeliveryProgressExport(
                id=p.id,
                deliverable_id=p.deliverable_id,
                status=p.status.value,
                percent_complete=p.percent_complete,
                comment=p.comment,
                revised_date=p.revised_date,
                acceptance_confirmed=p.acceptance_confirmed,
            )
            for p in progresses
        ],
    )


async def _build_gp_project(db: AsyncSession, project: Project) -> ProjectAsGpExport:
    baselines = list(
        (await db.execute(select(Baseline).where(Baseline.project_id == project.id)))
        .scalars().all()
    )
    baseline_exports: list[BaselineExport] = []
    for b in baselines:
        deliverables = list(
            (await db.execute(select(Deliverable).where(Deliverable.baseline_id == b.id)))
            .scalars().all()
        )
        baseline_exports.append(
            BaselineExport(
                id=b.id,
                proposal_id=b.proposal_id,
                status=b.status.value,
                activated_at=b.activated_at,
                payload=dict(b.payload or {}),
                created_at=b.created_at,
                deliverables=[
                    DeliverableExport(
                        id=d.id,
                        code=d.code,
                        title=d.title,
                        description=d.description,
                        phase=d.phase,
                        category=d.category.value if d.category else None,
                        complexity=d.complexity.value if d.complexity else None,
                        type=d.type.value if d.type else None,
                        due_date=d.due_date,
                        status=d.status.value,
                        acceptance_criteria=d.acceptance_criteria,
                        order_index=d.order_index,
                        created_at=d.created_at,
                    )
                    for d in deliverables
                ],
            )
        )

    reports = list(
        (await db.execute(select(Report).where(Report.project_id == project.id)))
        .scalars().all()
    )
    report_exports = [await _build_report_export(db, r) for r in reports]

    approvals: list[ReportApproval] = []
    if reports:
        report_ids = [r.id for r in reports]
        approvals = list(
            (
                await db.execute(
                    select(ReportApproval).where(ReportApproval.report_id.in_(report_ids))
                )
            ).scalars().all()
        )

    scope_changes = list(
        (
            await db.execute(
                select(ScopeChange).where(ScopeChange.project_id == project.id)
            )
        ).scalars().all()
    )

    agent_runs = list(
        (
            await db.execute(
                select(AgentRunLog).where(AgentRunLog.project_id == project.id)
            )
        ).scalars().all()
    )

    return ProjectAsGpExport(
        id=project.id,
        name=project.name,
        client_name=project.client_name,
        description=project.description,
        status=project.status.value,
        started_at=project.started_at,
        ended_at=project.ended_at,
        health_score_cached=project.health_score_cached,
        created_at=project.created_at,
        baselines=baseline_exports,
        reports=report_exports,
        approvals=[
            ApprovalExport(
                id=a.id,
                report_id=a.report_id,
                approver_id=a.approver_id,
                stage=a.stage.value,
                decision=a.decision.value,
                comment=a.comment,
                decided_at=a.decided_at,
            )
            for a in approvals
        ],
        scope_changes=[
            ScopeChangeExport(
                id=s.id,
                description=s.description,
                baseline_from_id=s.baseline_from_id,
                baseline_to_id=s.baseline_to_id,
                change_type=s.change_type.value if s.change_type else None,
                deliverable_code=s.deliverable_code,
                status=s.status.value,
                requested_at=s.requested_at,
                decided_at=s.decided_at,
                approved_by_id=s.approved_by_id,
            )
            for s in scope_changes
        ],
        agent_run_logs=[
            AgentRunLogExport(
                run_id=a.run_id,
                task_type=a.task_type.value,
                project_id=a.project_id,
                proposal_id=a.proposal_id,
                report_id=a.report_id,
                engine_used=a.engine_used,
                route_used=a.route_used,
                status=a.status.value,
                duration_s=a.duration_s,
                created_at=a.created_at,
                completed_at=a.completed_at,
            )
            for a in agent_runs
        ],
    )


async def _build_client_project(
    db: AsyncSession, project: Project, subject_id: uuid.UUID
) -> ProjectAsClientExport:
    reports = list(
        (
            await db.execute(
                select(Report)
                .where(Report.project_id == project.id)
                .where(Report.status.in_(_CLIENT_VISIBLE_REPORT_STATUSES))
            )
        ).scalars().all()
    )
    report_exports = [await _build_report_export(db, r) for r in reports]

    approvals: list[ReportApproval] = []
    if reports:
        report_ids = [r.id for r in reports]
        approvals = list(
            (
                await db.execute(
                    select(ReportApproval)
                    .where(ReportApproval.report_id.in_(report_ids))
                    .where(ReportApproval.approver_id == subject_id)
                )
            ).scalars().all()
        )

    return ProjectAsClientExport(
        id=project.id,
        name=project.name,
        client_name=project.client_name,
        description=project.description,
        status=project.status.value,
        started_at=project.started_at,
        ended_at=project.ended_at,
        reports=report_exports,
        approvals=[
            ApprovalExport(
                id=a.id,
                report_id=a.report_id,
                approver_id=a.approver_id,
                stage=a.stage.value,
                decision=a.decision.value,
                comment=a.comment,
                decided_at=a.decided_at,
            )
            for a in approvals
        ],
    )


def _render_readme(*, subject: User, extracted_at: datetime) -> str:
    """Texto humano dentro do ZIP. Aponta para a política e para o DPO.

    Mantido em PT-BR — público é o titular, que assina contrato em português.
    """
    return (
        "Exportação de dados pessoais — Sistema de Report Jump\n"
        "=====================================================\n"
        "\n"
        f"Titular: {subject.name} <{subject.email}> (id={subject.id})\n"
        f"Extração: {extracted_at.isoformat()} (UTC)\n"
        "\n"
        "Conteúdo do arquivo ZIP:\n"
        "  me.json                       — dados de cadastro do titular\n"
        "  projects_as_gp.json           — projetos em que o titular é Gerente de\n"
        "                                  Projeto (GP), com Reports (qualquer status),\n"
        "                                  Risks, ActionPlans, PendingItems, Approvals,\n"
        "                                  ScopeChanges, Deliverables, Baselines e\n"
        "                                  AgentRunLog associados\n"
        "  projects_as_client.json       — projetos em que o titular é cliente, com\n"
        "                                  Reports apenas em CLIENT_RELEASED/ARCHIVED\n"
        "                                  e Approvals em que o titular foi o\n"
        "                                  aprovador. Sem AgentRunLog (uso interno).\n"
        "  data_processing_records.json  — histórico LGPD do titular\n"
        "\n"
        "Base legal: LGPD art. 18 incisos II e V (acesso e portabilidade).\n"
        "Política aplicável: docs/lgpd.md no repositório do Sistema.\n"
        "Encarregado (DPO): Christopher Tominaga"
        " <christopher.tominaga@jumplabel.com.br>.\n"
        "Canal LGPD operacional: anderson.argentoni@jumplabel.com.br.\n"
        "\n"
        "Em caso de dúvida sobre o conteúdo ou pedido de retificação/eliminação,\n"
        "responda este e-mail citando o id do titular acima.\n"
    )


async def build_export_zip(db: AsyncSession, subject: User) -> bytes:
    """Monta o ZIP completo do titular. Retorna bytes prontos para Response.

    Não cria DataProcessingRecord aqui — esse log de auditoria é
    responsabilidade do endpoint chamador (caminho/role/timing diferem).
    """
    me = UserExport(
        id=subject.id,
        name=subject.name,
        email=subject.email,
        role=subject.role.value,
        created_at=subject.created_at,
        anonymized_at=subject.anonymized_at,
    )

    gp_projects = list(
        (await db.execute(select(Project).where(Project.gp_user_id == subject.id)))
        .scalars().all()
    )
    gp_exports = [await _build_gp_project(db, p) for p in gp_projects]

    client_projects = list(
        (await db.execute(select(Project).where(Project.client_user_id == subject.id)))
        .scalars().all()
    )
    client_exports = [
        await _build_client_project(db, p, subject.id) for p in client_projects
    ]

    dp_records = list(
        (
            await db.execute(
                select(DataProcessingRecord)
                .where(DataProcessingRecord.subject_user_id == subject.id)
                .order_by(DataProcessingRecord.requested_at)
            )
        ).scalars().all()
    )
    dp_exports = [
        DataProcessingRecordExport(
            id=r.id,
            request_type=r.request_type.value,
            status=r.status.value,
            requested_at=r.requested_at,
            fulfilled_at=r.fulfilled_at,
            notes=r.notes,
        )
        for r in dp_records
    ]

    extracted_at = datetime.now(UTC)
    files: dict[str, bytes] = {
        "me.json": json.dumps(
            _dump(me), ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8"),
        "projects_as_gp.json": json.dumps(
            [_dump(p) for p in gp_exports],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8"),
        "projects_as_client.json": json.dumps(
            [_dump(p) for p in client_exports],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8"),
        "data_processing_records.json": json.dumps(
            [_dump(r) for r in dp_exports],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8"),
        "README.txt": _render_readme(
            subject=subject, extracted_at=extracted_at
        ).encode("utf-8"),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            zf.writestr(name, files[name])
    return buf.getvalue()


__all__ = ["build_export_zip"]
