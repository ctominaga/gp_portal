"""Smoke do modelo de domínio: cria todas as tabelas em SQLite e instancia
exemplares mínimos de cada entidade.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import FlushError

from app.models import (
    ActionPlan,
    AgentRunLog,
    AgentRunStatus,
    AIInsight,
    ApprovalDecision,
    ApprovalStage,
    Baseline,
    BaselineStatus,
    DataProcessingRecord,
    Deliverable,
    DeliverableComplexity,
    DeliveryProgress,
    DPRequestStatus,
    DPRequestType,
    InsightScope,
    PendingItem,
    ProgressStatus,
    Project,
    ProjectRetrospective,
    Proposal,
    ProposalStatus,
    RAGStatus,
    Report,
    ReportApproval,
    ReportStatus,
    Risk,
    RiskImpact,
    RiskProbability,
    Role,
    ScopeChange,
    TaskType,
    User,
    WorkerHeartbeat,
)


@pytest.mark.asyncio
async def test_all_tables_created_no_metadata(engine_test) -> None:
    """Importa todos os modelos e cria via Base.metadata.create_all (no conftest)."""
    from sqlalchemy import inspect

    async with engine_test.connect() as conn:
        result = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    expected = {
        "users",
        "projects",
        "proposals",
        "baselines",
        "deliverables",
        "reports",
        "delivery_progresses",
        "risks",
        "action_plans",
        "pending_items",
        "agent_run_logs",
        "ai_insights",
        "scope_changes",
        "worker_heartbeats",
        "report_approvals",
        "project_retrospectives",
        "data_processing_records",
    }
    missing = expected - set(result)
    assert not missing, f"tabelas ausentes: {missing}"


@pytest.mark.asyncio
async def test_inserir_full_chain_project_proposal_baseline_deliverable_report(
    db_session: AsyncSession,
) -> None:
    """Insere a cadeia completa Project → Proposal → Baseline → Deliverable + Report."""
    gp = User(name="GP", email="gp@x.com", password_hash="x", role=Role.GP)
    db_session.add(gp)
    await db_session.flush()

    project = Project(
        name="Migração SAS",
        client_name="Bradesco",
        gp_user_id=gp.id,
        started_at=date(2026, 5, 1),
    )
    db_session.add(project)
    await db_session.flush()

    proposal = Proposal(
        project_id=project.id,
        version=1,
        file_url="r2://bucket/a.pdf",
        file_sha256="a" * 64,
        original_filename="proposta.pdf",
        size_bytes=12345,
        status=ProposalStatus.EXTRACTED,
        uploaded_by_id=gp.id,
    )
    db_session.add(proposal)
    await db_session.flush()

    baseline = Baseline(
        project_id=project.id,
        proposal_id=proposal.id,
        status=BaselineStatus.DRAFT,
        payload={"summary": "x"},
    )
    db_session.add(baseline)
    await db_session.flush()

    deliv = Deliverable(
        baseline_id=baseline.id,
        code="d-001",
        title="Migrar Custos PD",
        phase="sprint-1",
        complexity=DeliverableComplexity.LOW,
    )
    db_session.add(deliv)
    await db_session.flush()

    report = Report(
        project_id=project.id,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 15),
        rag_status=RAGStatus.GREEN,
        status=ReportStatus.DRAFT,
        created_by_id=gp.id,
    )
    db_session.add(report)
    await db_session.flush()

    db_session.add_all(
        [
            DeliveryProgress(
                report_id=report.id,
                deliverable_id=deliv.id,
                status=ProgressStatus.IN_PROGRESS,
                percent_complete=40,
            ),
            Risk(
                report_id=report.id, description="atraso",
                probability=RiskProbability.ALTA, impact=RiskImpact.MEDIO,
            ),
            ActionPlan(report_id=report.id, description="reunir todos"),
            PendingItem(report_id=report.id, description="acesso DB", owner_party="client"),
            ScopeChange(project_id=project.id, description="novo módulo"),
            ReportApproval(
                report_id=report.id,
                approver_id=gp.id,
                stage=ApprovalStage.PMO,
                decision=ApprovalDecision.APPROVED,
            ),
        ]
    )
    await db_session.flush()
    await db_session.commit()

    # Reload e checa relacionamentos básicos
    loaded = await db_session.get(Project, project.id)
    assert loaded is not None
    assert loaded.client_name == "Bradesco"


@pytest.mark.asyncio
async def test_agent_run_log_idempotente_pelo_pk(db_session: AsyncSession) -> None:
    log = AgentRunLog(
        run_id="ext-prop-2026-05-07-001",
        task_type=TaskType.PROPOSAL_EXTRACTION,
        engine_used="claude",
        route_used="headless",
        status=AgentRunStatus.DONE,
        attempts=[{"engine": "claude", "route": "headless", "success": True}],
        duration_s=12.4,
        worker_id="worker-jump-01",
    )
    db_session.add(log)
    await db_session.commit()

    # Tentativa de inserir mesmo PK → IntegrityError
    dup = AgentRunLog(
        run_id="ext-prop-2026-05-07-001",
        task_type=TaskType.PROPOSAL_EXTRACTION,
        status=AgentRunStatus.RUNNING,
        attempts=[],
    )
    db_session.add(dup)
    with pytest.raises((IntegrityError, FlushError, InvalidRequestError)):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_worker_heartbeat_e_ai_insight_e_dpr(db_session: AsyncSession) -> None:
    db_session.add(
        WorkerHeartbeat(
            worker_id="worker-jump-01",
            last_seen_at=datetime.now(UTC),
            status="ok",
            jobs_processed_today=5,
            jobs_failed_today=0,
        )
    )
    db_session.add(
        AIInsight(scope=InsightScope.PORTFOLIO, payload={"pattern": "backlog crescente"})
    )
    db_session.add(
        DataProcessingRecord(
            subject_external_email="cliente@bradesco.com.br",
            request_type=DPRequestType.EXPORT,
            status=DPRequestStatus.PENDING,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_unique_proposal_version_por_projeto(db_session: AsyncSession) -> None:
    gp = User(name="GP", email="g2@x.com", password_hash="x", role=Role.GP)
    db_session.add(gp)
    await db_session.flush()
    project = Project(name="P", client_name="X", gp_user_id=gp.id)
    db_session.add(project)
    await db_session.flush()

    p1 = Proposal(
        project_id=project.id, version=1, file_url="a", file_sha256="a" * 64,
        original_filename="a.pdf", size_bytes=1, uploaded_by_id=gp.id,
    )
    db_session.add(p1)
    await db_session.commit()

    p2 = Proposal(
        project_id=project.id, version=1, file_url="b", file_sha256="b" * 64,
        original_filename="b.pdf", size_bytes=1, uploaded_by_id=gp.id,
    )
    db_session.add(p2)
    with pytest.raises((IntegrityError, FlushError, InvalidRequestError)):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_project_retrospective_one_per_project(db_session: AsyncSession) -> None:
    gp = User(name="GP", email="g3@x.com", password_hash="x", role=Role.GP)
    db_session.add(gp)
    await db_session.flush()
    project = Project(name="P3", client_name="X", gp_user_id=gp.id)
    db_session.add(project)
    await db_session.flush()

    db_session.add(
        ProjectRetrospective(project_id=project.id, created_by_id=gp.id, lessons_learned="ok")
    )
    await db_session.commit()

    db_session.add(
        ProjectRetrospective(project_id=project.id, created_by_id=gp.id, lessons_learned="dup")
    )
    with pytest.raises((IntegrityError, FlushError, InvalidRequestError)):
        await db_session.commit()
    await db_session.rollback()
