"""F5.2: ScopeChange ganha baseline_from/to_id + change_type + approved_by_id (v3.1 §10.5).

Refactor para versionamento formal de escopo. Estrutura nova:
  - `baseline_from_id` (FK baselines, nullable) — baseline origem
  - `baseline_to_id`   (FK baselines, nullable) — baseline destino. Substitui
    `impact_baseline_id` semanticamente; backfill copia o valor.
  - `change_type`      (String(20), nullable) — added | removed | modified
  - `approved_by_id`   (FK users, nullable)  — quem decidiu no fluxo PMO

`impact_baseline_id` segue na tabela como DEPRECATED — não é mais escrito
por código novo. Remoção planejada para commit futuro depois de zero
leitura confirmada (combinado com user).

Backfill SQL idempotente (re-rodável; só preenche colunas NULL):
  1. `baseline_to_id ← impact_baseline_id` quando NULL e legacy preenchido
  2. `change_type` derivado do prefixo da description:
        "Adicionado: ..."  → 'ADDED'
        "Removido: ..."    → 'REMOVED'
        outros             → NULL (não chuta MODIFIED — só ADDED/REMOVED
                              eram criados em F4.3 pelo `diff_baselines` legacy)
  3. `baseline_from_id` ← baseline imediatamente anterior do mesmo projeto
     (created_at mais recente entre as anteriores ao baseline_to)

NOTA sobre case dos valores de enum: SAEnum no projeto (sem `values_callable`)
armazena o **name** do membro do Python enum (UPPERCASE). Por isso o backfill
insere 'ADDED'/'REMOVED' (não 'added'/'removed'). Ver `app/models/domain.py`
`ScopeChangeType` e os enums irmãos (BaselineStatus, etc.) que seguem o mesmo
padrão.

`BaselineStatus.REJECTED` foi adicionado ao Python enum nesta mesma
fase, mas `baselines.status` é `String(20)` (não native enum no PG, vide
0003), então nenhuma alteração SQL é necessária aqui.

Revision ID: 0014_scope_change_refactor
Revises: 0013_pendingitem_impact_created
Create Date: 2026-05-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_scope_change_refactor"
down_revision: Union[str, None] = "0013_pendingitem_impact_created"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Etapas do backfill — extraídas como SQL puro para permitir teste pytest
# direto (vide tests/test_migration_0014_scope_change.py). Idempotente: cada
# UPDATE só toca colunas ainda NULL, então rodar 2x não causa estrago.

_BACKFILL_BASELINE_TO = """
UPDATE scope_changes
   SET baseline_to_id = impact_baseline_id
 WHERE baseline_to_id IS NULL AND impact_baseline_id IS NOT NULL
"""

_BACKFILL_CHANGE_TYPE_ADDED = """
UPDATE scope_changes
   SET change_type = 'ADDED'
 WHERE change_type IS NULL AND description LIKE 'Adicionado:%'
"""

_BACKFILL_CHANGE_TYPE_REMOVED = """
UPDATE scope_changes
   SET change_type = 'REMOVED'
 WHERE change_type IS NULL AND description LIKE 'Removido:%'
"""

# Para cada scope_change com baseline_to_id preenchido, encontra a baseline
# imediatamente anterior do mesmo projeto (max created_at entre as < baseline_to).
# Funciona em Postgres e SQLite (correlated subquery padrão).
_BACKFILL_BASELINE_FROM = """
UPDATE scope_changes
   SET baseline_from_id = (
       SELECT b.id FROM baselines b
        WHERE b.project_id = (
              SELECT project_id FROM baselines
               WHERE id = scope_changes.baseline_to_id
              )
          AND b.id != scope_changes.baseline_to_id
          AND b.created_at < (
              SELECT created_at FROM baselines
               WHERE id = scope_changes.baseline_to_id
              )
        ORDER BY b.created_at DESC
        LIMIT 1
       )
 WHERE baseline_to_id IS NOT NULL AND baseline_from_id IS NULL
"""


def run_backfill(conn) -> dict[str, int]:
    """Executa o backfill em 4 etapas. Retorna rows afetadas por etapa.

    Idempotente — re-execução não modifica linhas já preenchidas. Reusado
    em pytest (SQLite) via importlib, vide `test_migration_0014_scope_change.py`.
    """
    return {
        "baseline_to_id": conn.execute(sa.text(_BACKFILL_BASELINE_TO)).rowcount,
        "change_type_added": conn.execute(sa.text(_BACKFILL_CHANGE_TYPE_ADDED)).rowcount,
        "change_type_removed": conn.execute(sa.text(_BACKFILL_CHANGE_TYPE_REMOVED)).rowcount,
        "baseline_from_id": conn.execute(sa.text(_BACKFILL_BASELINE_FROM)).rowcount,
    }


def upgrade() -> None:
    op.add_column(
        "scope_changes",
        sa.Column(
            "baseline_from_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("baselines.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "scope_changes",
        sa.Column(
            "baseline_to_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("baselines.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "scope_changes",
        sa.Column("change_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "scope_changes",
        sa.Column(
            "approved_by_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    run_backfill(op.get_bind())


def downgrade() -> None:
    op.drop_column("scope_changes", "approved_by_id")
    op.drop_column("scope_changes", "change_type")
    op.drop_column("scope_changes", "baseline_to_id")
    op.drop_column("scope_changes", "baseline_from_id")
