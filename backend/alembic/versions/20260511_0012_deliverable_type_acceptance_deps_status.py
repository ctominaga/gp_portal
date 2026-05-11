"""F5.1: Deliverable ganha type+acceptance_criteria+dependencies+status (v3.1 §4.2.2/§6.4.1).

Também realinha enums semanticamente para o vocabulário do prompt v1:
- `DeliverableComplexity` (3 valores `low/medium/high` → 5 PT-BR `baixa/baixa-media/media/media-alta/alta`)
- `category` muda de String(100) livre para enum `DeliverableCategory` (5 valores PT-BR)

Ambas as colunas (`complexity`, `category`) usam `native_enum=False` no
SQLAlchemy, então no Postgres são VARCHAR — não há `ALTER TYPE`. Mudança
de enum acontece só na camada Python. COUNT(*) FROM deliverables = 0
(mesma situação de Risk/F5.1).

Novos campos:
- `type`: nullable (nem todo deliverable tem tipo no baseline antigo)
- `acceptance_criteria`: nullable
- `dependencies`: JSON `list[str]` NOT NULL com server_default `'[]'`
- `status`: NOT NULL com server_default `'not_started'`

Revision ID: 0012_deliverable_fields
Revises: 0011_actionplan_objective_links
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_deliverable_fields"
down_revision: Union[str, None] = "0011_actionplan_objective_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 4 colunas novas. `dependencies` e `status` são NOT NULL com server_default
    # provisório (mesma estratégia das migrations anteriores F5.1).
    op.add_column(
        "deliverables",
        sa.Column("type", sa.String(40), nullable=True),
    )
    op.add_column(
        "deliverables",
        sa.Column("acceptance_criteria", sa.Text, nullable=True),
    )
    op.add_column(
        "deliverables",
        sa.Column(
            "dependencies",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "deliverables",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="not_started",
        ),
    )
    # Remove server_defaults para forçar valor explícito nas próximas inserções.
    op.alter_column("deliverables", "dependencies", server_default=None)
    op.alter_column("deliverables", "status", server_default=None)


def downgrade() -> None:
    op.drop_column("deliverables", "status")
    op.drop_column("deliverables", "dependencies")
    op.drop_column("deliverables", "acceptance_criteria")
    op.drop_column("deliverables", "type")
