"""F5.2 commit 5 — cobertura dos endpoints adicionados em commit 4.

Cobre:
  - GET /scope-changes (portfólio-wide, PMO/OPERATOR only)
  - Campo `pending_transitions_count` no `PortfolioProjectCard`
  - Validação Pydantic: reject sem comment não-vazio → 422
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
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


async def _login(client: AsyncClient, *, role: str, email: str) -> str:
    await client.post(
        "/auth/register",
        json={"name": role.title(), "email": email, "password": "JumpDev123!", "role": role},
    )
    r = await client.post("/auth/login", json={"email": email, "password": "JumpDev123!"})
    return r.json()["access_token"]


async def _seed_project_with_baseline_pair(
    db, *, gp_email: str, name: str = "P"
) -> tuple[Project, Baseline, Baseline]:
    gp = User(name="GP", email=gp_email, password_hash=hash_password("JumpDev123!"), role=Role.GP)
    db.add(gp)
    await db.flush()
    project = Project(name=name, client_name=f"C-{name}", gp_user_id=gp.id)
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


def _make_sc(
    project_id, baseline_to_id, *, change_type=ScopeChangeType.ADDED,
    status=ScopeChangeStatus.PROPOSED, code="d-001",
) -> ScopeChange:
    return ScopeChange(
        project_id=project_id,
        description=f"Adicionado: {code} · Migrar X",
        change_type=change_type,
        deliverable_code=code,
        baseline_to_id=baseline_to_id,
        status=status,
    )


# ---------- GET /scope-changes portfólio-wide ----------


@pytest.mark.asyncio
async def test_list_portfolio_scope_changes_multi_project_pmo(
    client: AsyncClient, db_session
) -> None:
    """PMO vê 3 ScopeChanges PROPOSED de 2 projetos diferentes."""
    pA, _, b2A = await _seed_project_with_baseline_pair(
        db_session, gp_email="gp-pA@x.com", name="Bradesco"
    )
    pB, _, b2B = await _seed_project_with_baseline_pair(
        db_session, gp_email="gp-pB@x.com", name="Itau"
    )
    db_session.add_all([
        _make_sc(pA.id, b2A.id, code="d-001"),
        _make_sc(pA.id, b2A.id, code="d-002", change_type=ScopeChangeType.MODIFIED),
        _make_sc(pB.id, b2B.id, code="d-101", change_type=ScopeChangeType.REMOVED),
    ])
    await db_session.commit()
    tok = await _login(client, role="PMO", email="pmo-port@x.com")

    r = await client.get(
        "/scope-changes", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 3
    project_ids = {item["project_id"] for item in body}
    assert project_ids == {str(pA.id), str(pB.id)}
    assert all(item["status"] == "proposed" for item in body)


@pytest.mark.asyncio
async def test_list_portfolio_filter_implemented(
    client: AsyncClient, db_session
) -> None:
    """Filtro status=implemented retorna só implementados (não PROPOSED)."""
    p, _, b2 = await _seed_project_with_baseline_pair(db_session, gp_email="gp-i@x.com")
    db_session.add_all([
        _make_sc(p.id, b2.id, code="d-1", status=ScopeChangeStatus.PROPOSED),
        _make_sc(p.id, b2.id, code="d-2", status=ScopeChangeStatus.IMPLEMENTED),
        _make_sc(p.id, b2.id, code="d-3", status=ScopeChangeStatus.IMPLEMENTED),
    ])
    await db_session.commit()
    tok = await _login(client, role="PMO", email="pmo-i@x.com")

    r = await client.get(
        "/scope-changes?status=implemented",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert all(item["status"] == "implemented" for item in body)


@pytest.mark.asyncio
async def test_list_portfolio_default_is_proposed(
    client: AsyncClient, db_session
) -> None:
    p, _, b2 = await _seed_project_with_baseline_pair(db_session, gp_email="gp-def@x.com")
    db_session.add_all([
        _make_sc(p.id, b2.id, code="d-1", status=ScopeChangeStatus.PROPOSED),
        _make_sc(p.id, b2.id, code="d-2", status=ScopeChangeStatus.REJECTED),
    ])
    await db_session.commit()
    tok = await _login(client, role="PMO", email="pmo-def@x.com")

    # Sem query param — default = proposed
    r = await client.get("/scope-changes", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["status"] == "proposed"
    assert body[0]["deliverable_code"] == "d-1"


@pytest.mark.asyncio
async def test_list_portfolio_403_for_gp(client: AsyncClient, db_session) -> None:
    p, _, b2 = await _seed_project_with_baseline_pair(db_session, gp_email="gp-block@x.com")
    db_session.add(_make_sc(p.id, b2.id))
    await db_session.commit()
    gp_tok = await _login(client, role="GP", email="gp-block@x.com")
    r = await client.get(
        "/scope-changes", headers={"Authorization": f"Bearer {gp_tok}"}
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_portfolio_403_for_client(client: AsyncClient, db_session) -> None:
    cli_tok = await _login(client, role="CLIENT", email="cli-block@x.com")
    r = await client.get(
        "/scope-changes", headers={"Authorization": f"Bearer {cli_tok}"}
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_portfolio_200_for_operator(
    client: AsyncClient, db_session
) -> None:
    p, _, b2 = await _seed_project_with_baseline_pair(db_session, gp_email="gp-op@x.com")
    db_session.add(_make_sc(p.id, b2.id))
    await db_session.commit()
    op_tok = await _login(client, role="OPERATOR", email="op@x.com")
    r = await client.get(
        "/scope-changes", headers={"Authorization": f"Bearer {op_tok}"}
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


# ---------- pending_transitions_count no PortfolioProjectCard ----------


@pytest.mark.asyncio
async def test_portfolio_overview_pending_transitions_count(
    client: AsyncClient, db_session
) -> None:
    """A=2 PROPOSED+1 IMPLEMENTED → count=2. B=0 PROPOSED → count=0."""
    pA, _, b2A = await _seed_project_with_baseline_pair(
        db_session, gp_email="gp-pA-cnt@x.com", name="Bradesco SAS"
    )
    pB, _, _ = await _seed_project_with_baseline_pair(
        db_session, gp_email="gp-pB-cnt@x.com", name="Itau Datalake"
    )
    db_session.add_all([
        _make_sc(pA.id, b2A.id, code="d-1", status=ScopeChangeStatus.PROPOSED),
        _make_sc(pA.id, b2A.id, code="d-2", status=ScopeChangeStatus.PROPOSED),
        _make_sc(pA.id, b2A.id, code="d-3", status=ScopeChangeStatus.IMPLEMENTED),
    ])
    await db_session.commit()
    tok = await _login(client, role="PMO", email="pmo-cnt@x.com")

    r = await client.get(
        "/portfolio", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200, r.text
    by_id = {p["project_id"]: p for p in r.json()["projects"]}
    assert by_id[str(pA.id)]["pending_transitions_count"] == 2
    assert by_id[str(pB.id)]["pending_transitions_count"] == 0


@pytest.mark.asyncio
async def test_portfolio_overview_count_five(
    client: AsyncClient, db_session
) -> None:
    p, _, b2 = await _seed_project_with_baseline_pair(
        db_session, gp_email="gp-5@x.com", name="P5"
    )
    db_session.add_all([
        _make_sc(p.id, b2.id, code=f"d-{i}", status=ScopeChangeStatus.PROPOSED)
        for i in range(5)
    ])
    await db_session.commit()
    tok = await _login(client, role="PMO", email="pmo-5@x.com")
    r = await client.get("/portfolio", headers={"Authorization": f"Bearer {tok}"})
    by_id = {p["project_id"]: p for p in r.json()["projects"]}
    assert by_id[str(p.id)]["pending_transitions_count"] == 5


# ---------- Validação Pydantic do comment reject ----------


@pytest.mark.asyncio
async def test_reject_empty_comment_returns_422(
    client: AsyncClient, db_session
) -> None:
    p, _, b2 = await _seed_project_with_baseline_pair(
        db_session, gp_email="gp-rej1@x.com"
    )
    db_session.add(_make_sc(p.id, b2.id, code="d-1"))
    await db_session.commit()
    tok = await _login(client, role="PMO", email="pmo-rej1@x.com")

    r = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {tok}"},
        json={"decision": "reject", "comment": ""},
    )
    assert r.status_code == 422
    assert "comment" in r.text.lower()


@pytest.mark.asyncio
async def test_reject_whitespace_only_comment_returns_422(
    client: AsyncClient, db_session
) -> None:
    p, _, b2 = await _seed_project_with_baseline_pair(
        db_session, gp_email="gp-rej2@x.com"
    )
    db_session.add(_make_sc(p.id, b2.id, code="d-1"))
    await db_session.commit()
    tok = await _login(client, role="PMO", email="pmo-rej2@x.com")

    r = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {tok}"},
        json={"decision": "reject", "comment": " \n  \t "},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reject_with_valid_comment_returns_200(
    client: AsyncClient, db_session
) -> None:
    p, _, b2 = await _seed_project_with_baseline_pair(
        db_session, gp_email="gp-rej3@x.com"
    )
    db_session.add(_make_sc(p.id, b2.id, code="d-1"))
    await db_session.commit()
    tok = await _login(client, role="PMO", email="pmo-rej3@x.com")

    r = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {tok}"},
        json={"decision": "reject", "comment": "motivo válido"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["baseline_status"] == "rejected"


@pytest.mark.asyncio
async def test_approve_without_comment_returns_200(
    client: AsyncClient, db_session
) -> None:
    """approve sem comment é OK — aprovação tácita é caso de uso válido."""
    p, _, b2 = await _seed_project_with_baseline_pair(
        db_session, gp_email="gp-app@x.com"
    )
    db_session.add(_make_sc(p.id, b2.id, code="d-1"))
    await db_session.commit()
    tok = await _login(client, role="PMO", email="pmo-app@x.com")

    r = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {tok}"},
        json={"decision": "approve"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["baseline_status"] == "active"
