"""F5.7: coluna users.anonymized_at + índice parcial (LGPD piloto).

LGPD art. 16 / direito de eliminação. Anonimização é o caminho escolhido
(Q1 da ADR de abertura F5.7) — usuário deixa de ser identificável mas FKs
históricas (Project.gp_user_id, Risk.owner_id, Approval.approver_id, etc.)
permanecem íntegras. `anonymized_at IS NOT NULL` marca o registro como
anonimizado; login guard em `/auth/login` rejeita autenticação a partir
desse ponto (texto idêntico ao de senha errada para não vazar informação).

Índice parcial só sobre registros anonimizados — cardinalidade alta e
benefício no admin: dashboards filtrando "anonimizados nos últimos 30 dias"
varrem só essa partição. Em SQLite (testes) também é suportado a partir
do 3.8.0; passamos as duas variantes (postgresql_where / sqlite_where) e
o alembic seleciona conforme o dialect.

Revision ID: 0018_users_anonymized_at
Revises: 0017_report_prepopulated_flag
Create Date: 2026-05-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_users_anonymized_at"
down_revision: Union[str, None] = "0017_report_prepopulated_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEX_NAME = "ix_users_anonymized_at_not_null"
_WHERE_CLAUSE = sa.text("anonymized_at IS NOT NULL")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        _INDEX_NAME,
        "users",
        ["anonymized_at"],
        unique=False,
        postgresql_where=_WHERE_CLAUSE,
        sqlite_where=_WHERE_CLAUSE,
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="users")
    op.drop_column("users", "anonymized_at")
