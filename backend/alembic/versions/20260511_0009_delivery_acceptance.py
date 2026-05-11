"""F4 / AJUSTE I: DeliveryProgress.acceptance_confirmed (spec v3.1 §4.2.2).

Adiciona coluna que persiste a resposta do modal "Critério de aceite foi
atingido?". Nullable: progressos parciais (status != done OU percent < 100)
não passam pelo modal e ficam com NULL.

Revision ID: 0009_delivery_acceptance
Revises: 0008_drop_old_health_weights
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_delivery_acceptance"
down_revision: Union[str, None] = "0008_drop_old_health_weights"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "delivery_progresses",
        sa.Column("acceptance_confirmed", sa.Boolean, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("delivery_progresses", "acceptance_confirmed")
