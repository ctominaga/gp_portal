"""F4: portfolio_config + in_app_notifications

Revision ID: 0005_portfolio_inapp
Revises: 0004_rag_dimensions
Create Date: 2026-05-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_portfolio_inapp"
down_revision: Union[str, None] = "0004_rag_dimensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("weight_progress", sa.Float, nullable=False, server_default="0.40"),
        sa.Column("weight_risks", sa.Float, nullable=False, server_default="0.20"),
        sa.Column("weight_pendings", sa.Float, nullable=False, server_default="0.20"),
        sa.Column("weight_schedule", sa.Float, nullable=False, server_default="0.20"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "in_app_notifications",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_in_app_notifications_user_unread",
        "in_app_notifications",
        ["user_id", "read_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_in_app_notifications_user_unread", table_name="in_app_notifications")
    op.drop_table("in_app_notifications")
    op.drop_table("portfolio_config")
