"""modelo de dominio completo (15 entidades)

Revision ID: 0003_domain
Revises: 0002_users
Create Date: 2026-05-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_domain"
down_revision: Union[str, None] = "0002_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("client_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("gp_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("started_at", sa.Date, nullable=True),
        sa.Column("ended_at", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "proposals",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(300), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_extraction"),
        sa.Column("uploaded_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("project_id", "version", name="uq_proposal_project_version"),
    )

    op.create_table(
        "baselines",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("proposal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # Apenas um baseline 'active' por projeto
    op.create_index(
        "uq_baseline_active_per_project",
        "baselines",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "deliverables",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("baseline_id", sa.Uuid(as_uuid=True), sa.ForeignKey("baselines.id"), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("phase", sa.String(100), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("complexity", sa.String(10), nullable=True),
        sa.Column("source_excerpt", sa.Text, nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("rag_status", sa.String(1), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("highlights", sa.Text, nullable=True),
        sa.Column("next_steps", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("health_score", sa.Float, nullable=True),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "delivery_progresses",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("report_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("deliverable_id", sa.Uuid(as_uuid=True), sa.ForeignKey("deliverables.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("percent_complete", sa.Integer, nullable=False, server_default="0"),
        sa.Column("comment", sa.Text, nullable=True),
        sa.UniqueConstraint("report_id", "deliverable_id", name="uq_progress_report_deliverable"),
        sa.CheckConstraint("percent_complete BETWEEN 0 AND 100", name="ck_progress_percent_range"),
    )

    op.create_table(
        "risks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("report_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "action_plans",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("report_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
    )

    op.create_table(
        "pending_items",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("report_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("owner_party", sa.String(50), nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
    )

    op.create_table(
        "agent_run_logs",
        sa.Column("run_id", sa.String(100), primary_key=True),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("proposal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("proposals.id"), nullable=True),
        sa.Column("report_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reports.id"), nullable=True),
        sa.Column("engine_used", sa.String(20), nullable=True),
        sa.Column("route_used", sa.String(20), nullable=True),
        sa.Column("failover_occurred", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("attempts", sa.JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("duration_s", sa.Float, nullable=True),
        sa.Column("worker_id", sa.String(100), nullable=True),
        sa.Column("artifact_path", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("failure_reason", sa.String(100), nullable=True),
        sa.Column("failure_detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "ai_insights",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("report_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reports.id"), nullable=True),
        sa.Column("agent_run_id", sa.String(100), sa.ForeignKey("agent_run_logs.run_id"), nullable=True),
        sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "scope_changes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("impact_baseline_id", sa.Uuid(as_uuid=True), sa.ForeignKey("baselines.id"), nullable=True),
    )

    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(100), primary_key=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ok"),
        sa.Column("sessions_status", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("jobs_processed_today", sa.Integer, nullable=False, server_default="0"),
        sa.Column("jobs_failed_today", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
    )

    op.create_table(
        "report_approvals",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("report_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("approver_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "project_retrospectives",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id"), unique=True, nullable=False),
        sa.Column("lessons_learned", sa.Text, nullable=True),
        sa.Column("kpis", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "data_processing_records",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("subject_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("subject_external_email", sa.String(254), nullable=True),
        sa.Column("request_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handled_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )


def downgrade() -> None:
    for table in (
        "data_processing_records",
        "project_retrospectives",
        "report_approvals",
        "worker_heartbeats",
        "scope_changes",
        "ai_insights",
        "agent_run_logs",
        "pending_items",
        "action_plans",
        "risks",
        "delivery_progresses",
        "reports",
        "deliverables",
        "baselines",
        "proposals",
        "projects",
    ):
        op.drop_table(table)
