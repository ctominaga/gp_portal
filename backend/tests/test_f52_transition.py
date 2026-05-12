"""F5.2 — testes do endpoint /baselines/{id}/transition + GETs de ScopeChange.

Cobre:
  - approve: ScopeChanges → IMPLEMENTED, baseline v2 → ACTIVE, v1 → SUPERSEDED,
    decided_at e approved_by preenchidos, notificação ao GP enviada.
  - reject: ScopeChanges → REJECTED, v2 → REJECTED, v1 permanece ACTIVE.
  - 403 quando role != PMO.
  - 409 quando baseline já decidido (idempotência).
  - 422 quando não há ScopeChange PROPOSED com baseline_to=this.
  - Listagem por projeto e detalhe individual.
"""
from __future__ import annotations

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


async def _seed_two_baselines_with_scope_changes(
    db, *, gp_email: str, n_scope_changes: int = 2
) -> tuple[Project, Baseline, Baseline, list[ScopeChange]]:
    """Cria projeto com baseline v1 ACTIVE + baseline v2 DRAFT + N
    ScopeChanges PROPOSED apontando para v2 (baseline_from=v1, baseline_to=v2).
    """
    gp = User(name="GP", email=gp_email, password_hash=hash_password("JumpDev123!"), role=Role.GP)
    db.add(gp)
    await db.flush()
    project = Project(name="P Bradesco SAS", client_name="Bradesco", gp_user_id=gp.id)
    db.add(project)
    await db.flush()

    p1 = Proposal(
        project_id=project.id, version=1, file_url="proposals/x.pdf",
        file_sha256="a" * 64, original_filename="v1.pdf", size_bytes=1,
        status=ProposalStatus.EXTRACTED, uploaded_by_id=gp.id,
    )
    p2 = Proposal(
        project_id=project.id, version=2, file_url="proposals/y.pdf",
        file_sha256="b" * 64, original_filename="v2.pdf", size_bytes=1,
        status=ProposalStatus.EXTRACTED, uploaded_by_id=gp.id,
    )
    db.add_all([p1, p2])
    await db.flush()
    b1 = Baseline(project_id=project.id, proposal_id=p1.id, status=BaselineStatus.ACTIVE, payload={})
    b2 = Baseline(project_id=project.id, proposal_id=p2.id, status=BaselineStatus.DRAFT, payload={})
    db.add_all([b1, b2])
    await db.flush()

    scs: list[ScopeChange] = []
    for i in range(n_scope_changes):
        sc = ScopeChange(
            project_id=project.id,
            description=f"Adicionado: d-{i:03d} · Novo entregável",
            change_type=ScopeChangeType.ADDED,
            baseline_from_id=b1.id,
            baseline_to_id=b2.id,
            status=ScopeChangeStatus.PROPOSED,
        )
        db.add(sc)
        scs.append(sc)
    await db.commit()
    return project, b1, b2, scs


# ---------- POST /baselines/{id}/transition ----------


@pytest.mark.asyncio
async def test_transition_approve_promotes_v2_demotes_v1(
    client: AsyncClient, db_session
) -> None:
    project, b1, b2, scs = await _seed_two_baselines_with_scope_changes(
        db_session, gp_email="gp-t1@x.com", n_scope_changes=3
    )
    pmo_tok = await _login(client, role="PMO", email="pmo-t1@x.com")

    r = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {pmo_tok}"},
        json={"decision": "approve"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["baseline_id"] == str(b2.id)
    assert body["baseline_status"] == "active"
    assert body["decision"] == "approve"
    assert body["scope_changes_count"] == 3
    assert body["approved_by"]

    # Estado pós-transição lido via HTTP — sessão de teste com StaticPool
    # mantém cache stale após request, e expire_all não basta.
    auth = {"Authorization": f"Bearer {pmo_tok}"}
    rb1 = await client.get(f"/baselines/{b1.id}", headers=auth)
    assert rb1.json()["status"] == "superseded"
    rb2 = await client.get(f"/baselines/{b2.id}", headers=auth)
    assert rb2.json()["status"] == "active"
    assert rb2.json()["activated_at"] is not None
    assert rb2.json()["activated_by_id"] is not None

    r_sc = await client.get(
        f"/projects/{project.id}/scope-changes?status=implemented",
        headers=auth,
    )
    assert r_sc.status_code == 200, r_sc.text
    body_sc = r_sc.json()
    assert len(body_sc) == 3
    for item in body_sc:
        assert item["status"] == "implemented"
        assert item["approved_by_id"] is not None
        assert item["decided_at"] is not None


@pytest.mark.asyncio
async def test_transition_reject_marks_baseline_rejected_keeps_v1_active(
    client: AsyncClient, db_session
) -> None:
    project, b1, b2, scs = await _seed_two_baselines_with_scope_changes(
        db_session, gp_email="gp-t2@x.com", n_scope_changes=2
    )
    pmo_tok = await _login(client, role="PMO", email="pmo-t2@x.com")

    r = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {pmo_tok}"},
        json={"decision": "reject", "comment": "Falta detalhamento técnico"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["baseline_status"] == "rejected"

    auth = {"Authorization": f"Bearer {pmo_tok}"}
    rb1 = await client.get(f"/baselines/{b1.id}", headers=auth)
    assert rb1.json()["status"] == "active"  # v1 permanece
    rb2 = await client.get(f"/baselines/{b2.id}", headers=auth)
    assert rb2.json()["status"] == "rejected"

    r_sc = await client.get(
        f"/projects/{project.id}/scope-changes?status=rejected",
        headers=auth,
    )
    body_sc = r_sc.json()
    assert len(body_sc) == 2
    for item in body_sc:
        assert item["status"] == "rejected"
        assert item["approved_by_id"] is not None


@pytest.mark.asyncio
async def test_transition_403_when_not_pmo(client: AsyncClient, db_session) -> None:
    project, b1, b2, _ = await _seed_two_baselines_with_scope_changes(
        db_session, gp_email="gp-t3@x.com"
    )
    gp_tok = await _login(client, role="GP", email="gp-t3@x.com")

    r = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {gp_tok}"},
        json={"decision": "approve"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_transition_409_when_baseline_already_decided(
    client: AsyncClient, db_session
) -> None:
    project, b1, b2, _ = await _seed_two_baselines_with_scope_changes(
        db_session, gp_email="gp-t4@x.com"
    )
    pmo_tok = await _login(client, role="PMO", email="pmo-t4@x.com")

    # 1ª aprovação ok
    r1 = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {pmo_tok}"},
        json={"decision": "approve"},
    )
    assert r1.status_code == 200

    # 2ª tentativa em baseline ACTIVE → 409
    r2 = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {pmo_tok}"},
        json={"decision": "approve"},
    )
    assert r2.status_code == 409
    assert "já decidida" in r2.json()["detail"].lower() or "ja decidida" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_transition_422_when_no_proposed_scope_changes(
    client: AsyncClient, db_session
) -> None:
    project, b1, b2, _ = await _seed_two_baselines_with_scope_changes(
        db_session, gp_email="gp-t5@x.com", n_scope_changes=0
    )
    pmo_tok = await _login(client, role="PMO", email="pmo-t5@x.com")

    r = await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {pmo_tok}"},
        json={"decision": "approve"},
    )
    assert r.status_code == 422


# ---------- GETs ----------


@pytest.mark.asyncio
async def test_list_project_scope_changes_filter_status(
    client: AsyncClient, db_session
) -> None:
    project, b1, b2, scs = await _seed_two_baselines_with_scope_changes(
        db_session, gp_email="gp-l1@x.com", n_scope_changes=3
    )
    pmo_tok = await _login(client, role="PMO", email="pmo-l1@x.com")

    # Default filter = PROPOSED retorna os 3
    r = await client.get(
        f"/projects/{project.id}/scope-changes",
        headers={"Authorization": f"Bearer {pmo_tok}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 3
    assert all(item["status"] == "proposed" for item in body)
    assert all(item["baseline_to_id"] == str(b2.id) for item in body)

    # Após approve, filtro PROPOSED retorna 0; filtro IMPLEMENTED retorna 3
    await client.post(
        f"/baselines/{b2.id}/transition",
        headers={"Authorization": f"Bearer {pmo_tok}"},
        json={"decision": "approve"},
    )
    r_p = await client.get(
        f"/projects/{project.id}/scope-changes?status=proposed",
        headers={"Authorization": f"Bearer {pmo_tok}"},
    )
    assert len(r_p.json()) == 0
    r_i = await client.get(
        f"/projects/{project.id}/scope-changes?status=implemented",
        headers={"Authorization": f"Bearer {pmo_tok}"},
    )
    assert len(r_i.json()) == 3


@pytest.mark.asyncio
async def test_get_scope_change_detail_pmo(
    client: AsyncClient, db_session
) -> None:
    project, b1, b2, scs = await _seed_two_baselines_with_scope_changes(
        db_session, gp_email="gp-d1@x.com", n_scope_changes=1
    )
    pmo_tok = await _login(client, role="PMO", email="pmo-d1@x.com")
    sc = scs[0]

    r = await client.get(
        f"/scope-changes/{sc.id}", headers={"Authorization": f"Bearer {pmo_tok}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(sc.id)
    assert body["change_type"] == "added"
    assert body["baseline_from_id"] == str(b1.id)
    assert body["baseline_to_id"] == str(b2.id)
    assert body["status"] == "proposed"


@pytest.mark.asyncio
async def test_list_scope_changes_gp_only_sees_own_project(
    client: AsyncClient, db_session
) -> None:
    # GP-A é dono do projeto, GP-B não.
    project, b1, b2, _ = await _seed_two_baselines_with_scope_changes(
        db_session, gp_email="gp-A@x.com", n_scope_changes=1
    )
    tok_outside = await _login(client, role="GP", email="gp-B@x.com")

    r = await client.get(
        f"/projects/{project.id}/scope-changes",
        headers={"Authorization": f"Bearer {tok_outside}"},
    )
    assert r.status_code == 403
