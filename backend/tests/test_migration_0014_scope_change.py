"""Tests do backfill da migration 0014 (F5.2 — ScopeChange refactor).

Como conftest.py usa `Base.metadata.create_all` (SQLite in-memory, sem
Alembic), o teste exercita a função `run_backfill` extraída na migration —
simulando registros legacy com `impact_baseline_id` + colunas novas NULL.

Cobre:
  - `baseline_to_id` ← `impact_baseline_id` (cópia direta)
  - `change_type` derivado do prefixo da description ("Adicionado:" →
    ADDED, "Removido:" → REMOVED). Descrições fora do padrão ficam NULL.
  - `baseline_from_id` ← baseline anterior do mesmo projeto.
  - Idempotência: rodar 2x não modifica linhas já preenchidas.
"""
from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Baseline,
    BaselineStatus,
    Project,
    Proposal,
    ProposalStatus,
    Role,
    ScopeChange,
    ScopeChangeStatus,
    ScopeChangeType,
    User,
)


def _load_migration_module():
    """Carrega a migration 0014 via importlib — nome do arquivo começa com
    dígito, então import normal não funciona."""
    mig_path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "20260511_0014_scope_change_refactor.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0014", mig_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _seed_legacy_scope_changes(
    db: AsyncSession,
) -> tuple[Project, dict[str, Baseline], dict[str, ScopeChange]]:
    """Cria 1 projeto, 3 baselines (v1, v2, v3) e 3 ScopeChange legacy:

      sc_added    — "Adicionado: d-001" linkado a v2 (esperado: from=v1, type=ADDED)
      sc_removed  — "Removido: d-002"   linkado a v3 (esperado: from=v2, type=REMOVED)
      sc_freeform — "Mudança geral"     linkado a v3 (esperado: from=v2, type=NULL)
    """
    gp = User(
        name="GP Teste",
        email="gp@jumplabel.com.br",
        password_hash="x",
        role=Role.GP,
    )
    db.add(gp)
    await db.flush()

    project = Project(
        name="P1", client_name="C1", gp_user_id=gp.id
    )
    db.add(project)
    await db.flush()

    base_t = datetime.now(UTC)
    baselines: dict[str, Baseline] = {}
    proposals: list[Proposal] = []
    for i, key in enumerate(("v1", "v2", "v3")):
        prop = Proposal(
            project_id=project.id,
            version=i + 1,
            file_url=f"proposals/{project.id}/v{i+1}.pdf",
            file_sha256="a" * 64,
            original_filename=f"v{i+1}.pdf",
            size_bytes=1,
            status=ProposalStatus.EXTRACTED,
            uploaded_by_id=gp.id,
        )
        db.add(prop)
        proposals.append(prop)
        await db.flush()
        b = Baseline(
            project_id=project.id,
            proposal_id=prop.id,
            status=(
                BaselineStatus.SUPERSEDED
                if key in ("v1", "v2")
                else BaselineStatus.DRAFT
            ),
            payload={},
            created_at=base_t + timedelta(minutes=i),
        )
        db.add(b)
        await db.flush()
        baselines[key] = b

    # 3 ScopeChange legacy — só `impact_baseline_id` + descrição. Demais
    # colunas novas (baseline_from/to_id, change_type) ficam NULL.
    sc_added = ScopeChange(
        project_id=project.id,
        description="Adicionado: d-001 · Migrar core",
        impact_baseline_id=baselines["v2"].id,
    )
    sc_removed = ScopeChange(
        project_id=project.id,
        description="Removido: d-002 · Tarefa descontinuada",
        impact_baseline_id=baselines["v3"].id,
    )
    sc_freeform = ScopeChange(
        project_id=project.id,
        description="Mudança geral no escopo solicitada pelo cliente",
        impact_baseline_id=baselines["v3"].id,
    )
    db.add_all([sc_added, sc_removed, sc_freeform])
    await db.commit()

    return project, baselines, {
        "added": sc_added,
        "removed": sc_removed,
        "freeform": sc_freeform,
    }


@pytest.mark.asyncio
async def test_backfill_classifies_and_links_legacy_scope_changes(
    db_session: AsyncSession,
) -> None:
    project, baselines, scs = await _seed_legacy_scope_changes(db_session)
    mig = _load_migration_module()

    # Snapshot inicial — todas colunas novas NULL.
    for sc in scs.values():
        await db_session.refresh(sc)
        assert sc.baseline_to_id is None
        assert sc.baseline_from_id is None
        assert sc.change_type is None

    # Roda o backfill com o mesmo bind da sessão (SQLite in-memory).
    raw_conn = await db_session.connection()
    counts = await raw_conn.run_sync(lambda sync_conn: mig.run_backfill(sync_conn))
    await db_session.commit()

    # Estatísticas reportadas (entram no resumo do commit).
    assert counts["baseline_to_id"] == 3
    assert counts["change_type_added"] == 1
    assert counts["change_type_removed"] == 1
    assert counts["baseline_from_id"] == 3

    # sc_added: linkado a v2 → from=v1, type=ADDED
    await db_session.refresh(scs["added"])
    assert scs["added"].baseline_to_id == baselines["v2"].id
    assert scs["added"].baseline_from_id == baselines["v1"].id
    assert scs["added"].change_type == ScopeChangeType.ADDED

    # sc_removed: linkado a v3 → from=v2, type=REMOVED
    await db_session.refresh(scs["removed"])
    assert scs["removed"].baseline_to_id == baselines["v3"].id
    assert scs["removed"].baseline_from_id == baselines["v2"].id
    assert scs["removed"].change_type == ScopeChangeType.REMOVED

    # sc_freeform: linkado a v3, description sem prefixo → type permanece NULL
    # (não chuta MODIFIED). baseline_from_id ainda é derivado.
    await db_session.refresh(scs["freeform"])
    assert scs["freeform"].baseline_to_id == baselines["v3"].id
    assert scs["freeform"].baseline_from_id == baselines["v2"].id
    assert scs["freeform"].change_type is None


@pytest.mark.asyncio
async def test_backfill_is_idempotent(db_session: AsyncSession) -> None:
    project, baselines, scs = await _seed_legacy_scope_changes(db_session)
    mig = _load_migration_module()

    raw_conn = await db_session.connection()
    first = await raw_conn.run_sync(lambda c: mig.run_backfill(c))
    await db_session.commit()

    raw_conn = await db_session.connection()
    second = await raw_conn.run_sync(lambda c: mig.run_backfill(c))
    await db_session.commit()

    # Segunda execução não modifica nada (todas as colunas já preenchidas
    # ou propositalmente NULL para descrições sem prefixo).
    assert second == {
        "baseline_to_id": 0,
        "change_type_added": 0,
        "change_type_removed": 0,
        "baseline_from_id": 0,
    }
    # Snapshot pós-2ª execução == pós-1ª
    await db_session.refresh(scs["added"])
    assert scs["added"].change_type == ScopeChangeType.ADDED
    assert scs["added"].baseline_to_id == baselines["v2"].id
    _ = first  # silencia ruff/lint
