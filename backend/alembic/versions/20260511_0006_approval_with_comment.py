"""F4 / AJUSTE A: trocar ApprovalDecision.REJECTED por APPROVED_WITH_COMMENT (spec v3.1 §10.1).

A coluna `report_approvals.decision` é `String(30)`, não enum nativo do Postgres,
então só precisamos atualizar dados. Registros legados com `decision='rejected'`
(se houver) viram `'requested_changes'` — semanticamente o caminho mais próximo
(também devolve o report para revisão).

Revision ID: 0006_approval_with_comment
Revises: 0005_portfolio_inapp
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006_approval_with_comment"
down_revision: Union[str, None] = "0005_portfolio_inapp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE report_approvals "
        "SET decision = 'requested_changes' "
        "WHERE decision = 'rejected'"
    )


def downgrade() -> None:
    # Não há reversão semântica: não dá pra distinguir um requested_changes
    # genuíno de um que veio de 'rejected'. Downgrade é no-op.
    pass
