"""F4 / AJUSTE B: dropar 4 colunas antigas de pesos do portfolio_config.

Conclui a migração iniciada na 0007. Após esta migration, o único campo de
pesos é `health_score_weights` JSONB. As 4 colunas antigas
(weight_progress/risks/pendings/schedule) já não são lidas pelo código.

Revision ID: 0008_drop_old_health_weights
Revises: 0007_health_score_5
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_drop_old_health_weights"
down_revision: Union[str, None] = "0007_health_score_5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("portfolio_config", "weight_progress")
    op.drop_column("portfolio_config", "weight_risks")
    op.drop_column("portfolio_config", "weight_pendings")
    op.drop_column("portfolio_config", "weight_schedule")


def downgrade() -> None:
    # Reverte ao schema da 0006 com defaults antigos.
    op.add_column(
        "portfolio_config",
        sa.Column("weight_progress", sa.Float, nullable=False, server_default="0.40"),
    )
    op.add_column(
        "portfolio_config",
        sa.Column("weight_risks", sa.Float, nullable=False, server_default="0.20"),
    )
    op.add_column(
        "portfolio_config",
        sa.Column("weight_pendings", sa.Float, nullable=False, server_default="0.20"),
    )
    op.add_column(
        "portfolio_config",
        sa.Column("weight_schedule", sa.Float, nullable=False, server_default="0.20"),
    )
