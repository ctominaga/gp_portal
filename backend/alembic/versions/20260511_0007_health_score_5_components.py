"""F4 / AJUSTE B: PortfolioConfig.health_score_weights JSONB + Project.health_score_cached (spec v3.1 §10.3).

Adiciona a coluna JSONB `health_score_weights` em `portfolio_config` com defaults
35/25/20/10/10 (rag_avg/spi/risk_inverse/resolution_rate/stability). Popula
a linha singleton existente. Adiciona `health_score_cached` em `projects` para
cache rápido do score atual.

As 4 colunas antigas (weight_progress/risks/pendings/schedule) continuam aqui;
serão dropadas na 0008. A separação em duas migrations segue regra clássica de
deploy seguro (adicionar → migrar consumidores → remover) e foi explicitada na
spec/instrução de execução desta fase.

Os pesos antigos NÃO migram numericamente para o novo JSONB: a fórmula da v3.1
substitui 3 dos 5 componentes (progress→rag_avg, schedule→spi, adiciona
stability), então pesos antigos não têm correspondência semântica. Defaults da
spec ancoram a configuração; PMO reajusta na tela se necessário (ADR
2026-05-11 em docs/decisoes.md).

Revision ID: 0007_health_score_5
Revises: 0006_approval_with_comment
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_health_score_5"
down_revision: Union[str, None] = "0006_approval_with_comment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DEFAULT_WEIGHTS_JSON = (
    '{"rag_avg": 0.35, "spi": 0.25, "risk_inverse": 0.20, '
    '"resolution_rate": 0.10, "stability": 0.10}'
)


def upgrade() -> None:
    op.add_column(
        "portfolio_config",
        sa.Column(
            "health_score_weights",
            sa.JSON,
            nullable=False,
            server_default=sa.text(f"'{_DEFAULT_WEIGHTS_JSON}'::json"),
        ),
    )
    # Singleton já existente: garante que tem os pesos novos (caso server_default
    # não tenha sido aplicado por já existir a linha em algumas instalações).
    op.execute(
        f"UPDATE portfolio_config SET health_score_weights = '{_DEFAULT_WEIGHTS_JSON}'::json "
        "WHERE health_score_weights IS NULL"
    )

    op.add_column(
        "projects",
        sa.Column("health_score_cached", sa.Float, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "health_score_cached")
    op.drop_column("portfolio_config", "health_score_weights")
