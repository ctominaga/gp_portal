"""F5.2: ScopeChange ganha deliverable_code (v3.1 §10.5 — commit 3).

Persiste o `code` do `Deliverable` afetado direto no ScopeChange. Motivação:
  - Chave de idempotência tripla de `diff_baselines` fica robusta:
    (baseline_to_id, change_type, deliverable_code), sem depender de
    parse da `description` que pode mudar de formato.
  - Joins futuros (ex: GET /scope-changes expandindo deliverable atual)
    não precisam reparsear texto livre.

Backfill por parse das descriptions legacy criadas pelo `diff_baselines`
de F4.3:
  "Adicionado: {code} · {title}"  → captura {code}
  "Removido: {code} · {title}"    → captura {code}
  Outros formatos                  → NULL (sem chute)

Mesma estratégia da 0014: idempotente, reusável em pytest via importlib.

Revision ID: 0015_scope_change_deliverable_code
Revises: 0014_scope_change_refactor
Create Date: 2026-05-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_scope_change_deliverable_code"
down_revision: Union[str, None] = "0014_scope_change_refactor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Captura o `code` que vem após "Adicionado: " ou "Removido: ", até o
# separador " · " (formato cunhado pelo `diff_baselines` em F4.3). SQL puro
# funciona em PG e SQLite. Em PG usa `substring(... from ... for ...)`,
# em SQLite usa `substr(... , ..., length)`. Para compatibilidade vou usar
# um approach mais simples: aproveitar o operador LIKE para filtrar e
# expressões padrão de string.

_BACKFILL_DELIVERABLE_CODE_ADDED = r"""
UPDATE scope_changes
   SET deliverable_code = TRIM(
       SUBSTR(
           description,
           LENGTH('Adicionado: ') + 1,
           CASE
               WHEN INSTR(SUBSTR(description, LENGTH('Adicionado: ') + 1), ' · ') > 0
                   THEN INSTR(SUBSTR(description, LENGTH('Adicionado: ') + 1), ' · ') - 1
               ELSE LENGTH(description)
           END
       )
   )
 WHERE deliverable_code IS NULL
   AND description LIKE 'Adicionado:%'
"""

_BACKFILL_DELIVERABLE_CODE_REMOVED = r"""
UPDATE scope_changes
   SET deliverable_code = TRIM(
       SUBSTR(
           description,
           LENGTH('Removido: ') + 1,
           CASE
               WHEN INSTR(SUBSTR(description, LENGTH('Removido: ') + 1), ' · ') > 0
                   THEN INSTR(SUBSTR(description, LENGTH('Removido: ') + 1), ' · ') - 1
               ELSE LENGTH(description)
           END
       )
   )
 WHERE deliverable_code IS NULL
   AND description LIKE 'Removido:%'
"""


def run_backfill(conn) -> dict[str, int]:
    """Executa o backfill por parse. Retorna rows afetadas em cada etapa.

    Idempotente: re-execução não modifica linhas com `deliverable_code` já
    preenchido. Descrições freeform (sem prefixo conhecido) permanecem NULL.
    """
    return {
        "deliverable_code_added": conn.execute(
            sa.text(_BACKFILL_DELIVERABLE_CODE_ADDED)
        ).rowcount,
        "deliverable_code_removed": conn.execute(
            sa.text(_BACKFILL_DELIVERABLE_CODE_REMOVED)
        ).rowcount,
    }


def upgrade() -> None:
    op.add_column(
        "scope_changes",
        sa.Column("deliverable_code", sa.String(50), nullable=True),
    )
    run_backfill(op.get_bind())


def downgrade() -> None:
    op.drop_column("scope_changes", "deliverable_code")
