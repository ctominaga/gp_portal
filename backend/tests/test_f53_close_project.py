"""F5.3 commit 2 — POST /projects/{id}/close + GET /projects/{id}/retrospective.

Cobre:
  - Happy path: GP-dono encerra com retrospectiva válida.
  - 403 quando não-GP / GP não-dono.
  - 422 quando faltam campos obrigatórios ou risk_id inválido.
  - 409 para cada item da cascata Q4 (7 cenários).
  - GET retrospective: GP-dono, PMO, CLIENT-dono, CLIENT-de-outro (403),
    404 quando projeto não foi encerrado ainda.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models import (
    Baseline,
    BaselineStatus,
    Project,
    ProjectRetrospective,
    ProjectStatus,
    Proposal,
    ProposalStatus,
    Report,
    ReportStatus,
    Risk,
    RiskImpact,
    RiskProbability,
    RiskStatus,
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


async def _seed_project_for_close(
    db, *, gp_email: str, client_email: str | None = None,
) -> tuple[Project, User]:
    """Cria projeto ACTIVE pronto para encerrar (sem bloqueios).

    Emails normalizados via `.lower()` — `auth/login` força lowercase no
    SELECT (vide auth.py), e o `auth/register` também armazena lowercase.
    Sem normalização aqui, `_login` falhava com 401 mesmo com user no DB.
    """
    gp = User(
        name="GP", email=gp_email.lower(),
        password_hash=hash_password("JumpDev123!"), role=Role.GP,
    )
    db.add(gp)
    await db.flush()
    client_id = None
    if client_email:
        cli = User(
            name="Cliente", email=client_email.lower(),
            password_hash=hash_password("JumpDev123!"), role=Role.CLIENT,
        )
        db.add(cli)
        await db.flush()
        client_id = cli.id
    project = Project(
        name="Bradesco SAS", client_name="Bradesco",
        gp_user_id=gp.id, client_user_id=client_id,
        status=ProjectStatus.ACTIVE,
    )
    db.add(project)
    await db.commit()
    return project, gp


def _retro_payload(materialized_risks: list[dict] | None = None) -> dict:
    return {
        "delivered_vs_proposed": "9/12 entregáveis aceitos. Sprint 4 fora.",
        "would_do_differently": "Plano de contingência regulatório no início.",
        "client_feedback": "Cliente satisfeito com governança.",
        "materialized_risks": materialized_risks or [],
    }


# ---------- Happy path ----------


@pytest.mark.asyncio
async def test_close_project_happy_path(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-c1@x.com")
    tok = await _login(client, role="GP", email="gp-c1@x.com")

    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=_retro_payload(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["project_id"] == str(project.id)
    assert body["status"] == "closed"
    assert body["ended_at"] == date.today().isoformat()
    assert body["retrospective"]["delivered_vs_proposed"].startswith("9/12")
    assert body["retrospective"]["materialized_risks"] == []

    # Estado pós: HTTP get reflete CLOSED
    r2 = await client.get(
        f"/projects/{project.id}", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r2.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_close_project_with_materialized_risks(client: AsyncClient, db_session) -> None:
    project, gp = await _seed_project_for_close(db_session, gp_email="gp-c2@x.com")
    # Cria um report já terminal (CLIENT_RELEASED não bloqueia) + um Risk materializado.
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="a" * 64,
        original_filename="p", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=gp.id,
    )
    db_session.add(proposal)
    await db_session.flush()
    report = Report(
        project_id=project.id, period_start=date(2026, 4, 1), period_end=date(2026, 4, 15),
        status=ReportStatus.CLIENT_RELEASED, created_by_id=gp.id,
    )
    db_session.add(report)
    await db_session.flush()
    risk = Risk(
        report_id=report.id, description="Bug regulatório",
        probability=RiskProbability.ALTA, impact=RiskImpact.ALTO,
        status=RiskStatus.MATERIALIZED,
    )
    db_session.add(risk)
    await db_session.commit()

    tok = await _login(client, role="GP", email="gp-c2@x.com")
    payload = _retro_payload(
        materialized_risks=[{"risk_id": str(risk.id), "comment": "Mitigado via task force"}]
    )
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=payload,
    )
    assert r.status_code == 200, r.text
    retro = r.json()["retrospective"]
    assert len(retro["materialized_risks"]) == 1
    assert retro["materialized_risks"][0]["risk_id"] == str(risk.id)
    assert retro["materialized_risks"][0]["comment"] == "Mitigado via task force"


# ---------- 403 ----------


@pytest.mark.asyncio
async def test_close_project_403_non_gp(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-x@x.com")
    pmo_tok = await _login(client, role="PMO", email="pmo-c@x.com")
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {pmo_tok}"},
        json=_retro_payload(),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_close_project_403_gp_not_owner(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-owner@x.com")
    # Outro GP loga
    other_tok = await _login(client, role="GP", email="gp-other@x.com")
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {other_tok}"},
        json=_retro_payload(),
    )
    assert r.status_code == 403
    assert "GP responsável" in r.json()["detail"]


# ---------- 422 ----------


@pytest.mark.asyncio
async def test_close_project_422_empty_field(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-422a@x.com")
    tok = await _login(client, role="GP", email="gp-422a@x.com")
    payload = _retro_payload()
    payload["delivered_vs_proposed"] = ""
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=payload,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_close_project_422_unknown_risk_id(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-422b@x.com")
    tok = await _login(client, role="GP", email="gp-422b@x.com")
    fake_id = str(uuid.uuid4())
    payload = _retro_payload(materialized_risks=[{"risk_id": fake_id, "comment": None}])
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=payload,
    )
    assert r.status_code == 422
    assert fake_id in r.json()["detail"]


@pytest.mark.asyncio
async def test_close_project_422_risk_from_other_project(
    client: AsyncClient, db_session
) -> None:
    # Projeto A (vou fechar)
    project_a, gp_a = await _seed_project_for_close(db_session, gp_email="gp-A422@x.com")
    # Projeto B (outro GP, contém um Risk)
    project_b, gp_b = await _seed_project_for_close(db_session, gp_email="gp-B422@x.com")
    prop_b = Proposal(
        project_id=project_b.id, version=1, file_url="y", file_sha256="b" * 64,
        original_filename="pb", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=gp_b.id,
    )
    db_session.add(prop_b)
    await db_session.flush()
    report_b = Report(
        project_id=project_b.id, period_start=date(2026, 4, 1), period_end=date(2026, 4, 15),
        status=ReportStatus.CLIENT_RELEASED, created_by_id=gp_b.id,
    )
    db_session.add(report_b)
    await db_session.flush()
    risk_b = Risk(
        report_id=report_b.id, description="Risk de B",
        probability=RiskProbability.MEDIA, impact=RiskImpact.MEDIO,
        status=RiskStatus.MATERIALIZED,
    )
    db_session.add(risk_b)
    await db_session.commit()

    tok_a = await _login(client, role="GP", email="gp-A422@x.com")
    payload = _retro_payload(
        materialized_risks=[{"risk_id": str(risk_b.id), "comment": "intruso"}]
    )
    r = await client.post(
        f"/projects/{project_a.id}/close",
        headers={"Authorization": f"Bearer {tok_a}"},
        json=payload,
    )
    assert r.status_code == 422
    assert str(risk_b.id) in r.json()["detail"]


# ---------- 409 cascata (7 cenários) ----------


@pytest.mark.asyncio
async def test_close_project_409_scope_change_pending(
    client: AsyncClient, db_session
) -> None:
    project, gp = await _seed_project_for_close(db_session, gp_email="gp-409a@x.com")
    db_session.add(
        ScopeChange(
            project_id=project.id, description="Adicionado: d-001 · X",
            change_type=ScopeChangeType.ADDED, deliverable_code="d-001",
            status=ScopeChangeStatus.PROPOSED,
        )
    )
    await db_session.commit()
    tok = await _login(client, role="GP", email="gp-409a@x.com")
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=_retro_payload(),
    )
    assert r.status_code == 409
    assert "transição" in r.json()["detail"].lower() or "transicao" in r.json()["detail"].lower()


@pytest.mark.parametrize("rstatus", [
    ReportStatus.DRAFT, ReportStatus.SUBMITTED,
    ReportStatus.PMO_APPROVED, ReportStatus.NEEDS_REVISION,
])
@pytest.mark.asyncio
async def test_close_project_409_report_in_flow(
    client: AsyncClient, db_session, rstatus
) -> None:
    project, gp = await _seed_project_for_close(
        db_session, gp_email=f"gp-409rep-{rstatus.value}@x.com"
    )
    db_session.add(
        Report(
            project_id=project.id, period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 15), status=rstatus, created_by_id=gp.id,
        )
    )
    await db_session.commit()
    tok = await _login(client, role="GP", email=f"gp-409rep-{rstatus.value}@x.com")
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=_retro_payload(),
    )
    assert r.status_code == 409
    assert "report" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_close_project_409_baseline_draft_v2(
    client: AsyncClient, db_session
) -> None:
    project, gp = await _seed_project_for_close(db_session, gp_email="gp-409bl@x.com")
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
    db_session.add_all([p1, p2])
    await db_session.flush()
    db_session.add(
        Baseline(project_id=project.id, proposal_id=p2.id, status=BaselineStatus.DRAFT, payload={})
    )
    await db_session.commit()
    tok = await _login(client, role="GP", email="gp-409bl@x.com")
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=_retro_payload(),
    )
    assert r.status_code == 409
    assert "baseline" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_close_project_409_paused(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-409p@x.com")
    project.status = ProjectStatus.PAUSED
    await db_session.commit()
    tok = await _login(client, role="GP", email="gp-409p@x.com")
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=_retro_payload(),
    )
    assert r.status_code == 409
    assert "pausado" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_close_project_409_already_closed(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-409c@x.com")
    project.status = ProjectStatus.CLOSED
    project.ended_at = date(2026, 5, 1)
    await db_session.commit()
    tok = await _login(client, role="GP", email="gp-409c@x.com")
    r = await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=_retro_payload(),
    )
    assert r.status_code == 409
    assert "encerrado" in r.json()["detail"].lower()
    assert "2026-05-01" in r.json()["detail"]


@pytest.mark.asyncio
async def test_close_project_404_missing_project(
    client: AsyncClient, db_session
) -> None:
    tok = await _login(client, role="GP", email="gp-404@x.com")
    fake_id = uuid.uuid4()
    r = await client.post(
        f"/projects/{fake_id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=_retro_payload(),
    )
    assert r.status_code == 404


# ---------- GET /retrospective ----------


@pytest.mark.asyncio
async def test_get_retrospective_404_when_not_closed(
    client: AsyncClient, db_session
) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-r404@x.com")
    tok = await _login(client, role="GP", email="gp-r404@x.com")
    r = await client.get(
        f"/projects/{project.id}/retrospective",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_retrospective_gp_owner(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-rgp@x.com")
    tok = await _login(client, role="GP", email="gp-rgp@x.com")
    await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {tok}"},
        json=_retro_payload(),
    )
    r = await client.get(
        f"/projects/{project.id}/retrospective",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["delivered_vs_proposed"].startswith("9/12")


@pytest.mark.asyncio
async def test_get_retrospective_pmo_ok(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_for_close(db_session, gp_email="gp-rpmo@x.com")
    gp_tok = await _login(client, role="GP", email="gp-rpmo@x.com")
    await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {gp_tok}"},
        json=_retro_payload(),
    )
    pmo_tok = await _login(client, role="PMO", email="pmo-r@x.com")
    r = await client.get(
        f"/projects/{project.id}/retrospective",
        headers={"Authorization": f"Bearer {pmo_tok}"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_retrospective_client_owner_ok(
    client: AsyncClient, db_session
) -> None:
    project, _ = await _seed_project_for_close(
        db_session, gp_email="gp-rcli@x.com", client_email="cli-r@x.com"
    )
    gp_tok = await _login(client, role="GP", email="gp-rcli@x.com")
    await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {gp_tok}"},
        json=_retro_payload(),
    )
    cli_tok = await _login(client, role="CLIENT", email="cli-r@x.com")
    r = await client.get(
        f"/projects/{project.id}/retrospective",
        headers={"Authorization": f"Bearer {cli_tok}"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_retrospective_client_outsider_403(
    client: AsyncClient, db_session
) -> None:
    project, _ = await _seed_project_for_close(
        db_session, gp_email="gp-rcli2@x.com", client_email="cli-r2@x.com"
    )
    gp_tok = await _login(client, role="GP", email="gp-rcli2@x.com")
    await client.post(
        f"/projects/{project.id}/close",
        headers={"Authorization": f"Bearer {gp_tok}"},
        json=_retro_payload(),
    )
    outsider_tok = await _login(client, role="CLIENT", email="cli-outsider@x.com")
    r = await client.get(
        f"/projects/{project.id}/retrospective",
        headers={"Authorization": f"Bearer {outsider_tok}"},
    )
    assert r.status_code == 403
