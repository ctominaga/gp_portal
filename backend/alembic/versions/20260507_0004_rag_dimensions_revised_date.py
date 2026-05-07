"""F3.5: rag por dimensao + revised_date + deviation_flag

Revision ID: 0004_rag_dimensions
Revises: 0003_domain
Create Date: 2026-05-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_rag_dimensions"
down_revision: Union[str, None] = "0003_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # reports: 3 dimensões + 3 justificativas
    op.add_column("reports", sa.Column("rag_prazo", sa.String(1), nullable=True))
    op.add_column("reports", sa.Column("rag_escopo", sa.String(1), nullable=True))
    op.add_column("reports", sa.Column("rag_qualidade", sa.String(1), nullable=True))
    op.add_column("reports", sa.Column("rag_prazo_justificativa", sa.Text, nullable=True))
    op.add_column("reports", sa.Column("rag_escopo_justificativa", sa.Text, nullable=True))
    op.add_column("reports", sa.Column("rag_qualidade_justificativa", sa.Text, nullable=True))

    # delivery_progresses: re-planejamento e flag
    op.add_column("delivery_progresses", sa.Column("revised_date", sa.Date, nullable=True))
    op.add_column(
        "delivery_progresses",
        sa.Column("deviation_flag", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("delivery_progresses", "deviation_flag")
    op.drop_column("delivery_progresses", "revised_date")
    op.drop_column("reports", "rag_qualidade_justificativa")
    op.drop_column("reports", "rag_escopo_justificativa")
    op.drop_column("reports", "rag_prazo_justificativa")
    op.drop_column("reports", "rag_qualidade")
    op.drop_column("reports", "rag_escopo")
    op.drop_column("reports", "rag_prazo")
