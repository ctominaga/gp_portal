"""Modelo de domínio do Sistema de Report da Jump.

Spec: `01_especificacao_funcional_v3.md` (seção 7.5 + fluxo 6.1) e o
agent-runner spec.

NOTA SOBRE COBERTURA DA SPEC:
A v3 prescreve schema explícito apenas para `AgentRunLog` e `WorkerHeartbeat`.
As demais entidades têm schemas inferidos a partir do fluxo funcional.
Campos marcados com `# TODO(v2.1)` precisam de confirmação cruzando com v2.1
quando ela for disponibilizada.
"""
from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------- ENUMS ----------


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class ProposalStatus(str, enum.Enum):
    PENDING_EXTRACTION = "pending_extraction"
    EXTRACTED = "extracted"
    NEEDS_OCR = "needs_ocr"
    SUPERSEDED = "superseded"
    EXTRACTION_FAILED = "extraction_failed"


class BaselineStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class DeliverableComplexity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReportStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PMO_APPROVED = "pmo_approved"
    CLIENT_RELEASED = "client_released"
    ARCHIVED = "archived"
    NEEDS_REVISION = "needs_revision"


class RAGStatus(str, enum.Enum):
    GREEN = "G"
    AMBER = "A"
    RED = "R"


class ProgressStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(str, enum.Enum):
    OPEN = "open"
    MITIGATED = "mitigated"
    CLOSED = "closed"


class ActionPlanStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class PendingItemStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class InsightScope(str, enum.Enum):
    PROJECT = "project"
    PORTFOLIO = "portfolio"


class ScopeChangeStatus(str, enum.Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


class TaskType(str, enum.Enum):
    """Spec v3 §7.4."""

    PROPOSAL_EXTRACTION = "proposal_extraction"
    REPORT_ANALYSIS = "report_analysis"
    PORTFOLIO_PATTERN = "portfolio_pattern"


class AgentRunStatus(str, enum.Enum):
    """Spec v3 §7.5 linha 347."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    EXPIRED = "expired"


class ApprovalStage(str, enum.Enum):
    PMO = "pmo"
    CLIENT = "client"


class ApprovalDecision(str, enum.Enum):
    APPROVED = "approved"
    APPROVED_WITH_COMMENT = "approved_with_comment"
    REQUESTED_CHANGES = "requested_changes"


class DPRequestType(str, enum.Enum):
    EXPORT = "export"
    DELETION = "deletion"
    ACCESS = "access"
    RECTIFICATION = "rectification"


class DPRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"


# ---------- ENTIDADES ----------


class Project(Base):
    """Projeto de consultoria. GP é o dono que produz reports; CLIENT vê portal."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    gp_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    client_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="project_status", native_enum=False),
        default=ProjectStatus.ACTIVE,
        nullable=False,
    )
    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    ended_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Cache do Health Score atual do projeto (spec v3.1 §10.3, recalculado a cada
    # submissão de report). Permite listagens rápidas no dashboard PMO sem
    # recomputar os 5 componentes a cada request.
    health_score_cached: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Proposal(Base):
    """PDF de proposta enviado pelo GP. Cada upload incrementa a versão."""

    __tablename__ = "proposals"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_proposal_project_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    file_url: Mapped[str] = mapped_column(String(500), nullable=False)  # R2 key ou path local
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(ProposalStatus, name="proposal_status", native_enum=False),
        default=ProposalStatus.PENDING_EXTRACTION,
        nullable=False,
    )

    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Baseline(Base):
    """Baseline de escopo extraído de uma Proposal. Apenas um `active` por projeto."""

    __tablename__ = "baselines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proposals.id"), nullable=False
    )

    status: Mapped[BaselineStatus] = mapped_column(
        SAEnum(BaselineStatus, name="baseline_status", native_enum=False),
        default=BaselineStatus.DRAFT,
        nullable=False,
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Snapshot do payload extraído (resumo executivo, premissas, fora-de-escopo, etc.)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Deliverable(Base):
    """Entregável dentro de uma Baseline. Editável durante a revisão GP."""

    __tablename__ = "deliverables"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    baseline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("baselines.id"), nullable=False
    )

    code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ex: 'd-001'
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    phase: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ex: 'sprint-1'
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    complexity: Mapped[DeliverableComplexity | None] = mapped_column(
        SAEnum(DeliverableComplexity, name="deliverable_complexity", native_enum=False),
        nullable=True,
    )

    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Report(Base):
    """Report executivo do GP. 7 seções (RAG, progresso, riscos, ações,
    pendências, destaques, próximos passos)."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # rag_status agregado (worst-of-3) — derivado das 3 dimensões abaixo
    rag_status: Mapped[RAGStatus | None] = mapped_column(
        SAEnum(RAGStatus, name="rag_status", native_enum=False), nullable=True
    )
    # Dimensões independentes do RAG (spec v3 §3.2.1)
    rag_prazo: Mapped[RAGStatus | None] = mapped_column(
        SAEnum(RAGStatus, name="rag_prazo", native_enum=False), nullable=True
    )
    rag_escopo: Mapped[RAGStatus | None] = mapped_column(
        SAEnum(RAGStatus, name="rag_escopo", native_enum=False), nullable=True
    )
    rag_qualidade: Mapped[RAGStatus | None] = mapped_column(
        SAEnum(RAGStatus, name="rag_qualidade", native_enum=False), nullable=True
    )
    # Justificativas — obrigatórias quando a dimensão for A ou R (validado em submit)
    rag_prazo_justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    rag_escopo_justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    rag_qualidade_justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, name="report_status", native_enum=False),
        default=ReportStatus.DRAFT,
        nullable=False,
    )

    # Seções textuais
    highlights: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Health score derivado (preenchido pelo backend após submissão)
    health_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeliveryProgress(Base):
    """Status de cada Deliverable dentro de um Report."""

    __tablename__ = "delivery_progresses"
    __table_args__ = (
        UniqueConstraint("report_id", "deliverable_id", name="uq_progress_report_deliverable"),
        CheckConstraint("percent_complete BETWEEN 0 AND 100", name="ck_progress_percent_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("reports.id"))
    deliverable_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deliverables.id")
    )

    status: Mapped[ProgressStatus] = mapped_column(
        SAEnum(ProgressStatus, name="progress_status", native_enum=False),
        default=ProgressStatus.PLANNED,
        nullable=False,
    )
    percent_complete: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Re-planejamento: GP marca nova data quando entrega não vai chegar no planned_date.
    # `deviation_flag` é derivado pelo backend ao comparar revised_date com
    # Deliverable.due_date. Spec runner §5.2.7.
    revised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deviation_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("reports.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, name="severity", native_enum=False), nullable=False
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[RiskStatus] = mapped_column(
        SAEnum(RiskStatus, name="risk_status", native_enum=False),
        default=RiskStatus.OPEN,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ActionPlan(Base):
    __tablename__ = "action_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("reports.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[ActionPlanStatus] = mapped_column(
        SAEnum(ActionPlanStatus, name="action_plan_status", native_enum=False),
        default=ActionPlanStatus.OPEN,
        nullable=False,
    )


class PendingItem(Base):
    """Item pendente que depende do cliente ou de terceiro — visível no portal."""

    __tablename__ = "pending_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("reports.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_party: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 'client'|'jump'|...
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PendingItemStatus] = mapped_column(
        SAEnum(PendingItemStatus, name="pending_item_status", native_enum=False),
        default=PendingItemStatus.OPEN,
        nullable=False,
    )


class AIInsight(Base):
    """Insights gerados por agentes de IA. Escopo project ou portfolio."""

    __tablename__ = "ai_insights"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    scope: Mapped[InsightScope] = mapped_column(
        SAEnum(InsightScope, name="insight_scope", native_enum=False), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("reports.id"), nullable=True
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("agent_run_logs.run_id"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ScopeChange(Base):
    __tablename__ = "scope_changes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ScopeChangeStatus] = mapped_column(
        SAEnum(ScopeChangeStatus, name="scope_change_status", native_enum=False),
        default=ScopeChangeStatus.PROPOSED,
        nullable=False,
    )
    impact_baseline_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("baselines.id"), nullable=True
    )


class AgentRunLog(Base):
    """Spec v3 §7.5 — log canônico de execução de agente.

    PK = run_id (string), garante idempotência. Retenção: 5 anos.
    """

    __tablename__ = "agent_run_logs"

    run_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    task_type: Mapped[TaskType] = mapped_column(
        SAEnum(TaskType, name="task_type", native_enum=False), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proposals.id"), nullable=True
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("reports.id"), nullable=True
    )

    engine_used: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'claude'|'codex'
    route_used: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'headless'|'broker'
    failover_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    attempts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)

    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[AgentRunStatus] = mapped_column(
        SAEnum(AgentRunStatus, name="agent_run_status", native_enum=False),
        default=AgentRunStatus.QUEUED,
        nullable=False,
    )
    failure_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkerHeartbeat(Base):
    """Spec v3 §7.5/8.1 — heartbeat dos workers (1 ou N máquinas)."""

    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")  # ok|degraded|down
    sessions_status: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    jobs_processed_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_failed_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReportApproval(Base):
    """Histórico do fluxo de aprovação de Report (PMO → CLIENT)."""

    __tablename__ = "report_approvals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("reports.id"))
    approver_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    stage: Mapped[ApprovalStage] = mapped_column(
        SAEnum(ApprovalStage, name="approval_stage", native_enum=False), nullable=False
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        SAEnum(ApprovalDecision, name="approval_decision", native_enum=False), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ProjectRetrospective(Base):
    __tablename__ = "project_retrospectives"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), unique=True
    )
    lessons_learned: Mapped[str | None] = mapped_column(Text, nullable=True)
    kpis: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


def _default_weights() -> dict[str, float]:
    """Pesos default do Health Score conforme spec v3.1 §10.3."""
    return {
        "rag_avg": 0.35,
        "spi": 0.25,
        "risk_inverse": 0.20,
        "resolution_rate": 0.10,
        "stability": 0.10,
    }


class PortfolioConfig(Base):
    """Configuração singleton do portfólio — pesos do Health Score (spec v3.1 §10.3).

    Apenas uma linha (id=1). JSONB com 5 componentes: rag_avg, spi, risk_inverse,
    resolution_rate, stability. Defaults 35/25/20/10/10 ancorados na spec.
    Soma esperada = 1.00 ± 0.01 (validada no serviço de update).
    """

    __tablename__ = "portfolio_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    health_score_weights: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=_default_weights
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class InAppNotification(Base):
    """Notificação in-app vinculada a um usuário."""

    __tablename__ = "in_app_notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class DataProcessingRecord(Base):
    """LGPD — registro de tratamento (RAT). SLA 15 dias."""

    __tablename__ = "data_processing_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_new_uuid)
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    subject_external_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    request_type: Mapped[DPRequestType] = mapped_column(
        SAEnum(DPRequestType, name="dp_request_type", native_enum=False), nullable=False
    )
    status: Mapped[DPRequestStatus] = mapped_column(
        SAEnum(DPRequestStatus, name="dp_request_status", native_enum=False),
        default=DPRequestStatus.PENDING,
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
