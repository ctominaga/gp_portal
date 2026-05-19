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

Backfill é feito em **Python** (não SQL) para portabilidade entre dialetos:
SQLite usa `INSTR/SUBSTR` mas Postgres não tem `INSTR` e a sintaxe de
`SUBSTR` difere. Parse Python contorna o problema e é trivialmente legível.

Revision ID: 0015_scope_change_deliverable_code
Revises: 0014_scope_change_refactor
Create Date: 2026-05-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_sc_delcode"
down_revision: Union[str, None] = "0014_scope_change_refactor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Prefixos cunhados pelo `diff_baselines` em F4.3. O par (prefix, status_key)
# alimenta o backfill genérico em `run_backfill`.
_BACKFILL_PREFIXES = (
    ("Adicionado: ", "deliverable_code_added"),
    ("Removido: ", "deliverable_code_removed"),
)

_SEPARATOR = " · "


def _extract_code(description: str, prefix: str) -> str | None:
    """Extrai o `code` de uma description no formato `{prefix}{code} · {title}`.

    Retorna None se o prefix não bate, ou string vazia depois do TRIM.
    """
    if not description.startswith(prefix):
        return None
    tail = description[len(prefix):]
    sep_pos = tail.find(_SEPARATOR)
    code = tail[:sep_pos] if sep_pos > 0 else tail
    code = code.strip()
    return code or None


def run_backfill(conn) -> dict[str, int]:
    """Executa o backfill por parse Python. Retorna rows afetadas por prefixo.

    Idempotente: re-execução não modifica linhas com `deliverable_code` já
    preenchido. Descrições freeform (sem prefixo conhecido) permanecem NULL.
    Portável entre Postgres e SQLite (parse em Python evita funções
    string específicas de dialeto).
    """
    counts: dict[str, int] = {key: 0 for _, key in _BACKFILL_PREFIXES}

    for prefix, status_key in _BACKFILL_PREFIXES:
        rows = conn.execute(
            sa.text(
                "SELECT id, description FROM scope_changes "
                "WHERE deliverable_code IS NULL "
                "AND description LIKE :pattern"
            ),
            {"pattern": f"{prefix}%"},
        ).fetchall()

        for row in rows:
            code = _extract_code(row.description, prefix)
            if code is None:
                continue
            conn.execute(
                sa.text(
                    "UPDATE scope_changes "
                    "SET deliverable_code = :code "
                    "WHERE id = :id"
                ),
                {"code": code, "id": row.id},
            )
            counts[status_key] += 1

    return counts


def upgrade() -> None:
    op.add_column(
        "scope_changes",
        sa.Column("deliverable_code", sa.String(50), nullable=True),
    )
    run_backfill(op.get_bind())


def downgrade() -> None:
    op.drop_column("scope_changes", "deliverable_code")
