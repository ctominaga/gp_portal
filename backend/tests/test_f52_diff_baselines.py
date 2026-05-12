"""F5.2 commit 3 — diff_baselines com MODIFIED + idempotência tripla.

Cobre:
  - ADDED: cria 1 ScopeChange ADDED por entregável novo (com baseline_from/to
    + change_type + deliverable_code preenchidos).
  - REMOVED: idem para entregáveis removidos.
  - MODIFIED (novo!): detecta divergência em campos relevantes (complexity,
    due_date, type, category, acceptance_criteria, dependencies, title, phase).
  - MODIFIED filtrado: divergência em campos NÃO-relevantes (description,
    source_excerpt, order_index) NÃO gera ScopeChange.
  - MIXED: 1 added + 1 removed + 1 modified em um único par de baselines.
  - Idempotência tripla por (baseline_to_id, change_type, deliverable_code).
  - Backfill da migration 0015 — parse "Adicionado: code · ..." e
    "Removido: code · ...", freeform fica NULL.
"""
from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.api.v1.client_portal import diff_baselines
from app.core.security import hash_password
from app.models import (
    Baseline,
    BaselineStatus,
    Deliverable,
    DeliverableCategory,
    DeliverableComplexity,
    DeliverableType,
    Project,
    Proposal,
    ProposalStatus,
    Role,
    ScopeChange,
    ScopeChangeStatus,
    ScopeChangeType,
    User,
)


def _load_mig_0015():
    p = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "20260512_0015_scope_change_deliverable_code.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0015", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _seed_two_baselines(db, *, gp_email: str = "gp-diff@x.com") -> tuple[
    Project, Baseline, Baseline
]:
    """Cria projeto + baseline v1 (ACTIVE) + baseline v2 (DRAFT), sem
    Deliverables — os testes individuais populam o que precisam."""
    gp = User(name="GP", email=gp_email, password_hash=hash_password("JumpDev123!"), role=Role.GP)
    db.add(gp)
    await db.flush()
    project = Project(name="P", client_name="C", gp_user_id=gp.id)
    db.add(project)
    await db.flush()
    p1 = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="a" * 64,
        original_filename="p1", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=gp.id,
    )
    p2 = Proposal(
        project_id=project.id, version=2, file_url="y", file_sha256="b" * 64,
        original_filename="p2", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=gp.id,
    )
    db.add_all([p1, p2])
    await db.flush()
    b1 = Baseline(project_id=project.id, proposal_id=p1.id, status=BaselineStatus.ACTIVE, payload={})
    b2 = Baseline(project_id=project.id, proposal_id=p2.id, status=BaselineStatus.DRAFT, payload={})
    db.add_all([b1, b2])
    await db.commit()
    return project, b1, b2


def _make_deliv(baseline_id: uuid.UUID, *, code: str, **kw) -> Deliverable:
    return Deliverable(
        baseline_id=baseline_id,
        code=code,
        title=kw.pop("title", f"Entregável {code}"),
        phase=kw.pop("phase", "fase-1"),
        complexity=kw.pop("complexity", DeliverableComplexity.MEDIUM),
        **kw,
    )


# ---------- ADDED / REMOVED / MIXED ----------


@pytest.mark.asyncio
async def test_added_only_creates_added_scope_changes(db_session) -> None:
    project, b1, b2 = await _seed_two_baselines(db_session, gp_email="gp-d1@x.com")
    db_session.add_all([
        _make_deliv(b1.id, code="d-001"),
        _make_deliv(b1.id, code="d-002"),
        _make_deliv(b2.id, code="d-001"),
        _make_deliv(b2.id, code="d-002"),
        _make_deliv(b2.id, code="d-003"),
        _make_deliv(b2.id, code="d-004"),
    ])
    await db_session.commit()

    result = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert result["scope_changes_created"] == 2

    rows = list(
        (
            await db_session.execute(
                select(ScopeChange).where(ScopeChange.baseline_to_id == b2.id)
            )
        ).scalars().all()
    )
    assert len(rows) == 2
    codes = {r.deliverable_code for r in rows}
    assert codes == {"d-003", "d-004"}
    for r in rows:
        assert r.change_type == ScopeChangeType.ADDED
        assert r.baseline_from_id == b1.id
        assert r.baseline_to_id == b2.id
        assert r.status == ScopeChangeStatus.PROPOSED


@pytest.mark.asyncio
async def test_removed_only_creates_removed_scope_changes(db_session) -> None:
    project, b1, b2 = await _seed_two_baselines(db_session, gp_email="gp-d2@x.com")
    db_session.add_all([
        _make_deliv(b1.id, code="d-001"),
        _make_deliv(b1.id, code="d-002"),
        _make_deliv(b1.id, code="d-003"),
        _make_deliv(b2.id, code="d-001"),
    ])
    await db_session.commit()

    result = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert result["scope_changes_created"] == 2
    rows = list(
        (
            await db_session.execute(
                select(ScopeChange).where(ScopeChange.baseline_to_id == b2.id)
            )
        ).scalars().all()
    )
    codes = {r.deliverable_code for r in rows}
    assert codes == {"d-002", "d-003"}
    for r in rows:
        assert r.change_type == ScopeChangeType.REMOVED


# ---------- MODIFIED (novo) ----------


@pytest.mark.asyncio
async def test_modified_complexity_creates_modified_scope_change(db_session) -> None:
    project, b1, b2 = await _seed_two_baselines(db_session, gp_email="gp-d3@x.com")
    db_session.add_all([
        _make_deliv(b1.id, code="d-001", complexity=DeliverableComplexity.MEDIUM),
        _make_deliv(b2.id, code="d-001", complexity=DeliverableComplexity.HIGH),
    ])
    await db_session.commit()

    result = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert result["scope_changes_created"] == 1
    row = (
        await db_session.execute(
            select(ScopeChange).where(ScopeChange.baseline_to_id == b2.id)
        )
    ).scalar_one()
    assert row.change_type == ScopeChangeType.MODIFIED
    assert row.deliverable_code == "d-001"
    assert "complexity" in row.description
    assert "media" in row.description and "alta" in row.description


@pytest.mark.asyncio
async def test_modified_due_date_creates_modified_scope_change(db_session) -> None:
    project, b1, b2 = await _seed_two_baselines(db_session, gp_email="gp-d4@x.com")
    db_session.add_all([
        _make_deliv(b1.id, code="d-002", due_date=date(2026, 3, 15)),
        _make_deliv(b2.id, code="d-002", due_date=date(2026, 4, 20)),
    ])
    await db_session.commit()

    result = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert result["scope_changes_created"] == 1
    row = (
        await db_session.execute(
            select(ScopeChange).where(ScopeChange.baseline_to_id == b2.id)
        )
    ).scalar_one()
    assert row.change_type == ScopeChangeType.MODIFIED
    assert "due_date" in row.description
    assert "2026-03-15" in row.description and "2026-04-20" in row.description


@pytest.mark.asyncio
async def test_modified_type_and_category_creates_modified_scope_change(db_session) -> None:
    project, b1, b2 = await _seed_two_baselines(db_session, gp_email="gp-d5@x.com")
    db_session.add_all([
        _make_deliv(
            b1.id, code="d-003",
            type=DeliverableType.CODE_MIGRATION,
            category=DeliverableCategory.TECHNICAL,
        ),
        _make_deliv(
            b2.id, code="d-003",
            type=DeliverableType.DOCUMENTATION,
            category=DeliverableCategory.GOVERNANCE,
        ),
    ])
    await db_session.commit()

    result = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert result["scope_changes_created"] == 1


@pytest.mark.asyncio
async def test_modified_ignored_when_only_non_relevant_fields_change(db_session) -> None:
    """description, source_excerpt e order_index não devem gerar MODIFIED."""
    project, b1, b2 = await _seed_two_baselines(db_session, gp_email="gp-d6@x.com")
    db_session.add_all([
        _make_deliv(
            b1.id, code="d-100",
            description="texto antigo",
            source_excerpt="trecho A",
            order_index=0,
        ),
        _make_deliv(
            b2.id, code="d-100",
            description="texto novo reescrito",
            source_excerpt="trecho B",
            order_index=5,
        ),
    ])
    await db_session.commit()

    result = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert result["scope_changes_created"] == 0


@pytest.mark.asyncio
async def test_mixed_added_removed_modified(db_session) -> None:
    project, b1, b2 = await _seed_two_baselines(db_session, gp_email="gp-d7@x.com")
    db_session.add_all([
        _make_deliv(b1.id, code="keep", title="igual"),
        _make_deliv(b1.id, code="bye", title="vai sair"),
        _make_deliv(b1.id, code="changes", complexity=DeliverableComplexity.MEDIUM),
        _make_deliv(b2.id, code="keep", title="igual"),
        _make_deliv(b2.id, code="changes", complexity=DeliverableComplexity.HIGH),
        _make_deliv(b2.id, code="new", title="recém-chegado"),
    ])
    await db_session.commit()

    result = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert result["scope_changes_created"] == 3
    by_type = {}
    rows = list(
        (
            await db_session.execute(
                select(ScopeChange).where(ScopeChange.baseline_to_id == b2.id)
            )
        ).scalars().all()
    )
    for r in rows:
        by_type.setdefault(r.change_type, []).append(r)
    assert len(by_type[ScopeChangeType.ADDED]) == 1
    assert by_type[ScopeChangeType.ADDED][0].deliverable_code == "new"
    assert len(by_type[ScopeChangeType.REMOVED]) == 1
    assert by_type[ScopeChangeType.REMOVED][0].deliverable_code == "bye"
    assert len(by_type[ScopeChangeType.MODIFIED]) == 1
    assert by_type[ScopeChangeType.MODIFIED][0].deliverable_code == "changes"


# ---------- Idempotência tripla ----------


@pytest.mark.asyncio
async def test_idempotence_triple_key_blocks_duplicates(db_session) -> None:
    project, b1, b2 = await _seed_two_baselines(db_session, gp_email="gp-d8@x.com")
    db_session.add_all([
        _make_deliv(b1.id, code="d-001", complexity=DeliverableComplexity.LOW),
        _make_deliv(b2.id, code="d-001", complexity=DeliverableComplexity.HIGH),
        _make_deliv(b2.id, code="d-NEW"),
    ])
    await db_session.commit()

    r1 = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert r1["scope_changes_created"] == 2  # 1 MODIFIED + 1 ADDED

    r2 = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert r2["scope_changes_created"] == 0

    rows = list(
        (
            await db_session.execute(
                select(ScopeChange).where(ScopeChange.baseline_to_id == b2.id)
            )
        ).scalars().all()
    )
    assert len(rows) == 2


# ---------- Migration 0015 — backfill deliverable_code ----------


@pytest.mark.asyncio
async def test_migration_0015_backfill_extracts_deliverable_code(db_session) -> None:
    project, b1, b2 = await _seed_two_baselines(db_session, gp_email="gp-mig@x.com")

    sc_added = ScopeChange(
        project_id=project.id,
        description="Adicionado: d-042 · Migrar tabela X",
        baseline_to_id=b2.id,
    )
    sc_removed = ScopeChange(
        project_id=project.id,
        description="Removido: d-007 · Tarefa cancelada",
        baseline_to_id=b2.id,
    )
    sc_freeform = ScopeChange(
        project_id=project.id,
        description="Cliente pediu re-priorização geral",
        baseline_to_id=b2.id,
    )
    db_session.add_all([sc_added, sc_removed, sc_freeform])
    await db_session.commit()

    mig = _load_mig_0015()
    raw = await db_session.connection()
    counts = await raw.run_sync(lambda c: mig.run_backfill(c))
    await db_session.commit()

    assert counts["deliverable_code_added"] == 1
    assert counts["deliverable_code_removed"] == 1

    await db_session.refresh(sc_added)
    await db_session.refresh(sc_removed)
    await db_session.refresh(sc_freeform)
    assert sc_added.deliverable_code == "d-042"
    assert sc_removed.deliverable_code == "d-007"
    assert sc_freeform.deliverable_code is None

    # Idempotência: rodar 2x não modifica nada.
    raw2 = await db_session.connection()
    counts2 = await raw2.run_sync(lambda c: mig.run_backfill(c))
    await db_session.commit()
    assert counts2 == {"deliverable_code_added": 0, "deliverable_code_removed": 0}
