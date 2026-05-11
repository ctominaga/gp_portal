"""F5.1: ActionPlan ganha objective + linked_risk_id + linked_deliverable_id (v3.1 §4.2.4).

`objective` é obrigatório (Text NOT NULL). Mesma estratégia da migration 0010
(F5.1 Risk): server_default='' temporário para a operação ALTER em si, removido
em seguida com `alter_column ... server_default=None` para forçar valor
explícito nas próximas inserções.

`linked_risk_id` e `linked_deliverable_id` são FKs nullable com ON DELETE
SET NULL — se o risco/deliverable vinculado for removido, o plano persiste
desvinculado (não desaparece junto). Os dois links são independentes: um plano
pode ter ambos, um, ou nenhum.

Revision ID: 0011_actionplan_objective_links
Revises: 0010_risk_p_i_level
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_actionplan_objective_links"
down_revision: Union[str, None] = "0010_risk_p_i_level"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `objective` Text NOT NULL — server_default='' apenas para a operação ALTER.
    # Removido logo depois para que próximas inserções venham com valor explícito.
    op.add_column(
        "action_plans",
        sa.Column("objective", sa.Text, nullable=False, server_default=""),
    )
    op.alter_column("action_plans", "objective", server_default=None)
    # Vinculações opcionais — ON DELETE SET NULL preserva o plano se o
    # risco/deliverable referenciado for removido.
    op.add_column(
        "action_plans",
        sa.Column(
            "linked_risk_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("risks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "action_plans",
        sa.Column(
            "linked_deliverable_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("deliverables.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("action_plans", "linked_deliverable_id")
    op.drop_column("action_plans", "linked_risk_id")
    op.drop_column("action_plans", "objective")
