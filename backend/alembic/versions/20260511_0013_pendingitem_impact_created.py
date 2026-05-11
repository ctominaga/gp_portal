"""F5.1: PendingItem ganha impact + created_at (v3.1 §4.2.5).

`impact` é Text nullable (descrição do que será afetado se não resolvido).
`created_at` é DateTime NOT NULL com `server_default=now()` permanente
(default do banco; padrão usado em outros models do projeto). Cumpre o
papel da "Data de abertura" descrita na spec — não duplicamos com campo
`open_date` separado.

COUNT(*) FROM pending_items investigado em F5.1 ETAPA 2A: zero. Adicionar
campo NOT NULL com server_default não bloqueia nada.

Revision ID: 0013_pendingitem_impact_created
Revises: 0012_deliverable_fields
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_pendingitem_impact_created"
down_revision: Union[str, None] = "0012_deliverable_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pending_items",
        sa.Column("impact", sa.Text, nullable=True),
    )
    # `server_default=now()` é permanente aqui: futuras inserções sem
    # `created_at` explícito recebem o timestamp do banco. Padrão do projeto
    # (outros models como `risks`, `action_plans` já fazem isso).
    op.add_column(
        "pending_items",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("pending_items", "created_at")
    op.drop_column("pending_items", "impact")
