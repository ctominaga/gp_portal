"""F5.4: flag is_prepopulated em risks/pending_items/delivery_progresses (v3.1 §10.2).

Modo de Report Assistido por IA — `prepopulate_report` cria filhos do novo
Report copiando do report anterior (Risks IDENTIFIED+MONITORING, PendingItems
OPEN) e criando placeholders de DeliveryProgress para Deliverables com prazo
no período. Flag `is_prepopulated=True` marca esses registros para o frontend
mostrar badge "do report anterior"; backend zera no PATCH quando o GP edita.

3 colunas idênticas (sa.Boolean NOT NULL default False). Sem backfill — registros
históricos são todos "manuais" (flag=False), default zero do server_default cuida.

Revision ID: 0017_report_prepopulated_flag
Revises: 0016_retrospective_schema
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_report_prepopulated_flag"
down_revision: Union[str, None] = "0016_retrospective_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES: tuple[str, ...] = ("risks", "pending_items", "delivery_progresses")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "is_prepopulated",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        # Remove server_default — código Python sempre passa valor explícito.
        # Server_default só serve à operação ALTER em si (registros legacy
        # ficam com False, semanticamente correto: nunca foram herdados).
        op.alter_column(table, "is_prepopulated", server_default=None)


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "is_prepopulated")
