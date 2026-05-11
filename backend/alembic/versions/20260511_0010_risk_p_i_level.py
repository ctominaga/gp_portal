"""F5.1: Risk drop severity, add probability+impact+mitigation_plan, new RiskStatus.

Spec v3.1 §4.2.3 prescreve matriz (probability × impact) com `level` derivado,
mais 4 estados de ciclo de vida (Identificado/Em monitoramento/Mitigado/
Materializado). Severity (low/medium/high/critical) era único campo; agora
`probability` (alta/media/baixa) e `impact` (alto/medio/baixo) são separados,
e o `level` (RiskLevel enum) vira property Python computada a cada acesso.

COUNT(*) FROM risks investigado em sessão de planejamento: zero (Docker daemon
off, ambiente pre-piloto). Drop+recreate sem backfill, sem cerimônia.

A coluna `status` é `String(20)` desde a 0003 (não native enum no Postgres),
então não há `ALTER TYPE` necessário — os valores aceitos mudam só do lado
do Python enum. Linhas órfãs com status=open/closed seriam aceitas no banco
mas falhariam no load Python; como não há linhas, sem problema.

Revision ID: 0010_risk_p_i_level
Revises: 0009_delivery_acceptance
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_risk_p_i_level"
down_revision: Union[str, None] = "0009_delivery_acceptance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop coluna antiga `severity` (Severity enum: low/medium/high/critical)
    op.drop_column("risks", "severity")
    # Adiciona eixos da matriz de risco — NOT NULL com server_default
    # provisório `media`/`medio` (Postgres exige default ao adicionar NOT NULL).
    # Como COUNT=0, server_default só serve para a operação ALTER em si.
    op.add_column(
        "risks",
        sa.Column(
            "probability",
            sa.String(10),
            nullable=False,
            server_default="media",
        ),
    )
    op.add_column(
        "risks",
        sa.Column(
            "impact",
            sa.String(10),
            nullable=False,
            server_default="medio",
        ),
    )
    op.add_column(
        "risks",
        sa.Column("mitigation_plan", sa.Text, nullable=True),
    )
    # Remove server_default para que próximas inserções venham com valor
    # explícito do código.
    op.alter_column("risks", "probability", server_default=None)
    op.alter_column("risks", "impact", server_default=None)


def downgrade() -> None:
    op.drop_column("risks", "mitigation_plan")
    op.drop_column("risks", "impact")
    op.drop_column("risks", "probability")
    op.add_column(
        "risks",
        sa.Column("severity", sa.String(10), nullable=False, server_default="medium"),
    )
    op.alter_column("risks", "severity", server_default=None)
