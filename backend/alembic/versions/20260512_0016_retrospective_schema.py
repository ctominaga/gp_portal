"""F5.3: ProjectRetrospective schema (drop+recreate) — v3.1 §10.4.

Schema novo:
  - `delivered_vs_proposed` (Text NOT NULL) — Entregue vs. Proposto
  - `would_do_differently`  (Text NOT NULL) — O que faria diferente
  - `client_feedback`       (Text NOT NULL) — Feedback do cliente
  - `materialized_risks`    (JSON NOT NULL default '[]') — lista de
    {risk_id, comment} (FK validation em camada Pydantic, não SQL)

Colunas removidas (schema antigo, divergente da spec):
  - `lessons_learned` (Text nullable) — texto único genérico
  - `kpis` (JSON) — campo livre sem prescrição na spec §10.4

Mantidas:
  - id, project_id (UNIQUE), created_by_id, created_at

Sobre `closed_at` listado na spec v3.1 §9.5:
  Não introduzido como coluna separada — cumprido semanticamente por
  `created_at` (registro só existe quando projeto é encerrado). Decisão
  documentada no docstring do modelo `ProjectRetrospective`.

Estratégia: drop+recreate sem cerimônia (mesmo padrão F5.1 Risk/Deliverable).
Investigação confirmou COUNT(*) = 0 em todas as instalações conhecidas —
endpoint `/close` nunca existiu, então a tabela só recebeu dados via
testes unitários efêmeros.

Revision ID: 0016_retrospective_schema
Revises: 0015_scope_change_deliverable_code
Create Date: 2026-05-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_retrospective_schema"
down_revision: Union[str, None] = "0015_scope_change_deliverable_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop colunas legacy
    op.drop_column("project_retrospectives", "lessons_learned")
    op.drop_column("project_retrospectives", "kpis")

    # Add colunas v3.1 §10.4. NOT NULL com server_default provisório
    # (Postgres exige default ao adicionar NOT NULL). COUNT=0 garante
    # que server_default só serve para a operação ALTER em si.
    op.add_column(
        "project_retrospectives",
        sa.Column(
            "delivered_vs_proposed", sa.Text, nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "project_retrospectives",
        sa.Column(
            "would_do_differently", sa.Text, nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "project_retrospectives",
        sa.Column(
            "client_feedback", sa.Text, nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "project_retrospectives",
        sa.Column(
            "materialized_risks", sa.JSON, nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )

    # Remove server_default das colunas Text — código Python sempre passa
    # valor explícito (validação Pydantic exige não-vazio em F5.3 commit 2).
    op.alter_column("project_retrospectives", "delivered_vs_proposed", server_default=None)
    op.alter_column("project_retrospectives", "would_do_differently", server_default=None)
    op.alter_column("project_retrospectives", "client_feedback", server_default=None)


def downgrade() -> None:
    op.drop_column("project_retrospectives", "materialized_risks")
    op.drop_column("project_retrospectives", "client_feedback")
    op.drop_column("project_retrospectives", "would_do_differently")
    op.drop_column("project_retrospectives", "delivered_vs_proposed")
    op.add_column(
        "project_retrospectives",
        sa.Column("lessons_learned", sa.Text, nullable=True),
    )
    op.add_column(
        "project_retrospectives",
        sa.Column(
            "kpis", sa.JSON, nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
