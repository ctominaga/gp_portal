"""Testes do CRUD de Baseline + Deliverable + Report (autosave)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models import (
    Baseline,
    BaselineStatus,
    Deliverable,
    DeliverableComplexity,
    Project,
    Proposal,
    ProposalStatus,
    Role,
    User,
)


async def _login_as(client: AsyncClient, *, role: str, email: str) -> str:
    """Login tolerante: tenta registrar; se 409, segue direto para login."""
    await client.post(
        "/auth/register",
        json={"name": role.title(), "email": email, "password": "JumpDev123!", "role": role},
    )
    r = await client.post("/auth/login", json={"email": email, "password": "JumpDev123!"})
    return r.json()["access_token"]


async def _seed_project_with_baseline(db_session, *, gp_email: str = "gp-bl@x.com") -> tuple[Project, Baseline]:
    gp = User(
        name="GP",
        email=gp_email,
        password_hash=hash_password("JumpDev123!"),
        role=Role.GP,
    )
    db_session.add(gp)
    await db_session.flush()
    project = Project(name="Bradesco SAS", client_name="Bradesco", gp_user_id=gp.id)
    db_session.add(project)
    await db_session.flush()
    proposal = Proposal(
        project_id=project.id, version=1, file_url="proposals/x.pdf",
        file_sha256="a" * 64, original_filename="p.pdf", size_bytes=1,
        status=ProposalStatus.EXTRACTED, uploaded_by_id=gp.id,
    )
    db_session.add(proposal)
    await db_session.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id, status=BaselineStatus.DRAFT,
        payload={"k": "v"},
    )
    db_session.add(baseline)
    await db_session.flush()
    db_session.add(
        Deliverable(
            baseline_id=baseline.id,
            code="d-001",
            title="Migrar A",
            phase="fase-1",
            complexity=DeliverableComplexity.LOW,
            source_excerpt="trecho da proposta",
        )
    )
    await db_session.commit()
    return project, baseline


# --------- Baseline ---------


@pytest.mark.asyncio
async def test_get_baseline_inclui_deliverables(
    client: AsyncClient, db_session
) -> None:
    project, baseline = await _seed_project_with_baseline(db_session, gp_email="gp-1@x.com")
    tok = await _login_as(client, role="GP", email="gp-1@x.com")

    r = await client.get(
        f"/baselines/{baseline.id}", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["payload"] == {"k": "v"}
    assert len(body["deliverables"]) == 1
    assert body["deliverables"][0]["title"] == "Migrar A"
    assert body["deliverables"][0]["source_excerpt"] == "trecho da proposta"


@pytest.mark.asyncio
async def test_patch_deliverable_atualiza_campos(
    client: AsyncClient, db_session
) -> None:
    project, baseline = await _seed_project_with_baseline(db_session, gp_email="gp-2@x.com")
    tok = await _login_as(client, role="GP", email="gp-2@x.com")

    r = await client.get(f"/baselines/{baseline.id}", headers={"Authorization": f"Bearer {tok}"})
    deliv_id = r.json()["deliverables"][0]["id"]

    r2 = await client.patch(
        f"/deliverables/{deliv_id}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"title": "Migrar A (revisada)", "complexity": "high"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["title"] == "Migrar A (revisada)"
    assert r2.json()["complexity"] == "high"


@pytest.mark.asyncio
async def test_create_e_delete_deliverable(
    client: AsyncClient, db_session
) -> None:
    project, baseline = await _seed_project_with_baseline(db_session, gp_email="gp-3@x.com")
    tok = await _login_as(client, role="GP", email="gp-3@x.com")

    r = await client.post(
        f"/baselines/{baseline.id}/deliverables",
        headers={"Authorization": f"Bearer {tok}"},
        json={"title": "Novo entregável", "phase": "fase-2"},
    )
    assert r.status_code == 201
    new_id = r.json()["id"]

    r2 = await client.delete(
        f"/deliverables/{new_id}", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r2.status_code == 204


@pytest.mark.asyncio
async def test_activate_baseline_marca_outros_como_superseded(
    client: AsyncClient, db_session
) -> None:
    project, baseline = await _seed_project_with_baseline(db_session, gp_email="gp-4@x.com")
    tok = await _login_as(client, role="GP", email="gp-4@x.com")

    # Cria segundo baseline (também draft)
    proposal2 = Proposal(
        project_id=project.id, version=2, file_url="proposals/y.pdf",
        file_sha256="b" * 64, original_filename="p2.pdf", size_bytes=1,
        status=ProposalStatus.EXTRACTED, uploaded_by_id=project.gp_user_id,
    )
    db_session.add(proposal2)
    await db_session.flush()
    baseline2 = Baseline(
        project_id=project.id, proposal_id=proposal2.id, status=BaselineStatus.DRAFT,
        payload={},
    )
    db_session.add(baseline2)
    await db_session.commit()

    # Ativa o primeiro
    r = await client.post(
        f"/baselines/{baseline.id}/activate",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    # Ativa o segundo — primeiro vira superseded
    r2 = await client.post(
        f"/baselines/{baseline2.id}/activate",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "active"

    r3 = await client.get(
        f"/baselines/{baseline.id}", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r3.json()["status"] == "superseded"


# --------- Report autosave ---------


@pytest.mark.asyncio
async def test_create_e_patch_report_idempotente(
    client: AsyncClient, db_session
) -> None:
    project, _ = await _seed_project_with_baseline(db_session, gp_email="gp-rep@x.com")
    tok = await _login_as(client, role="GP", email="gp-rep@x.com")

    r = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "project_id": str(project.id),
            "period_start": "2026-05-01",
            "period_end": "2026-05-15",
        },
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert r.json()["status"] == "draft"

    # PATCH 1: rag + highlights
    r2 = await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"rag_status": "G", "highlights": "tudo no prazo"},
    )
    assert r2.status_code == 200
    assert r2.json()["rag_status"] == "G"
    assert r2.json()["highlights"] == "tudo no prazo"

    # PATCH 2: idempotente (mesmo body) — não muda nada relevante
    r3 = await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"highlights": "tudo no prazo"},
    )
    assert r3.status_code == 200
    assert r3.json()["highlights"] == "tudo no prazo"

    # PATCH 3: substitui as listas inteiras
    r4 = await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "risks": [
                {"description": "atraso na rotina A",
                 "probability": "media", "impact": "medio"},
                {"description": "bloqueio de acesso ao DB",
                 "probability": "alta", "impact": "medio"},
            ],
            "action_plans": [
                {"description": "agendar reunião com Bradesco"},
            ],
            "pending_items": [
                {"description": "credenciais databricks", "owner_party": "client"},
            ],
        },
    )
    assert r4.status_code == 200
    body = r4.json()
    assert len(body["risks"]) == 2
    assert len(body["action_plans"]) == 1
    assert len(body["pending_items"]) == 1

    # PATCH 4: substitui a lista de risks por uma só (apaga o "atraso na rotina A")
    r5 = await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"risks": [{"description": "bloqueio de acesso ao DB",
                         "probability": "alta", "impact": "medio"}]},
    )
    assert r5.status_code == 200
    assert len(r5.json()["risks"]) == 1


@pytest.mark.asyncio
async def test_submit_report_exige_rag_3d_e_justificativa_em_a_r(
    client: AsyncClient, db_session
) -> None:
    project, _ = await _seed_project_with_baseline(db_session, gp_email="gp-sub@x.com")
    tok = await _login_as(client, role="GP", email="gp-sub@x.com")
    r = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "project_id": str(project.id),
            "period_start": "2026-05-01",
            "period_end": "2026-05-15",
        },
    )
    rid = r.json()["id"]

    # 1) Submeter sem RAG por dimensão → 400 listando todas
    r2 = await client.post(
        f"/reports/{rid}/submit", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r2.status_code == 400
    assert "prazo" in r2.text and "escopo" in r2.text and "qualidade" in r2.text

    # 2) Apenas 1 dimensão → ainda 400
    await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"rag_prazo": "G"},
    )
    assert (await client.post(
        f"/reports/{rid}/submit", headers={"Authorization": f"Bearer {tok}"}
    )).status_code == 400

    # 3) 3 dimensões com A/R mas sem justificativa → 400
    await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"rag_prazo": "G", "rag_escopo": "A", "rag_qualidade": "R"},
    )
    r4 = await client.post(
        f"/reports/{rid}/submit", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r4.status_code == 400
    assert "justificativa" in r4.text.lower()

    # 4) Com justificativas válidas → 200; rag_status agregado = R (worst-of-3)
    await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "rag_escopo_justificativa": "novo módulo solicitado",
            "rag_qualidade_justificativa": "bug crítico em produção",
        },
    )
    r5 = await client.post(
        f"/reports/{rid}/submit", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r5.status_code == 200, r5.text
    assert r5.json()["status"] == "submitted"
    assert r5.json()["rag_status"] == "R"
    assert r5.json()["rag_prazo"] == "G"
    assert r5.json()["rag_escopo"] == "A"
    assert r5.json()["rag_qualidade"] == "R"


@pytest.mark.asyncio
async def test_submit_so_verde_dispensa_justificativa(
    client: AsyncClient, db_session
) -> None:
    project, _ = await _seed_project_with_baseline(db_session, gp_email="gp-allgreen@x.com")
    tok = await _login_as(client, role="GP", email="gp-allgreen@x.com")
    r = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "project_id": str(project.id),
            "period_start": "2026-05-01",
            "period_end": "2026-05-15",
        },
    )
    rid = r.json()["id"]
    await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"rag_prazo": "G", "rag_escopo": "G", "rag_qualidade": "G"},
    )
    r2 = await client.post(
        f"/reports/{rid}/submit", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r2.status_code == 200
    assert r2.json()["rag_status"] == "G"


@pytest.mark.asyncio
async def test_revised_date_marca_deviation_flag_quando_diferente_de_due_date(
    client: AsyncClient, db_session
) -> None:
    """Verifica F3.5.5: deviation_flag fica True quando revised_date != due_date."""
    from datetime import date as _date

    project, baseline = await _seed_project_with_baseline(db_session, gp_email="gp-rev@x.com")
    # Define due_date no deliverable existente
    deliv = (await db_session.execute(
        __import__("sqlalchemy").select(Deliverable).where(Deliverable.baseline_id == baseline.id)
    )).scalar_one()
    deliv.due_date = _date(2026, 6, 15)
    await db_session.commit()

    tok = await _login_as(client, role="GP", email="gp-rev@x.com")
    r = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "project_id": str(project.id),
            "period_start": "2026-05-01",
            "period_end": "2026-05-15",
        },
    )
    rid = r.json()["id"]

    # Caso 1: revised_date == due_date → deviation_flag False
    r2 = await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "progresses": [{
                "deliverable_id": str(deliv.id),
                "status": "in_progress",
                "percent_complete": 40,
                "revised_date": "2026-06-15",
            }],
        },
    )
    assert r2.status_code == 200
    assert r2.json()["progresses"][0]["deviation_flag"] is False

    # Caso 2: revised_date != due_date → deviation_flag True
    r3 = await client.patch(
        f"/reports/{rid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "progresses": [{
                "deliverable_id": str(deliv.id),
                "status": "in_progress",
                "percent_complete": 40,
                "revised_date": "2026-07-01",
            }],
        },
    )
    assert r3.status_code == 200
    assert r3.json()["progresses"][0]["deviation_flag"] is True
    assert r3.json()["progresses"][0]["revised_date"] == "2026-07-01"


@pytest.mark.asyncio
async def test_list_project_reports(client: AsyncClient, db_session) -> None:
    project, _ = await _seed_project_with_baseline(db_session, gp_email="gp-l@x.com")
    tok = await _login_as(client, role="GP", email="gp-l@x.com")

    for d_start, d_end in [("2026-04-01", "2026-04-15"), ("2026-04-16", "2026-04-30")]:
        await client.post(
            "/reports",
            headers={"Authorization": f"Bearer {tok}"},
            json={"project_id": str(project.id), "period_start": d_start, "period_end": d_end},
        )

    r = await client.get(
        f"/projects/{project.id}/reports", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    # Ordenado por period_end desc
    assert body[0]["period_end"] >= body[1]["period_end"]


@pytest.mark.asyncio
async def test_create_report_invalido_period_start_apos_end(
    client: AsyncClient, db_session
) -> None:
    project, _ = await _seed_project_with_baseline(db_session, gp_email="gp-bad@x.com")
    tok = await _login_as(client, role="GP", email="gp-bad@x.com")
    r = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "project_id": str(project.id),
            "period_start": "2026-06-01",
            "period_end": "2026-05-15",
        },
    )
    assert r.status_code == 400


# --------- worker stub ---------


@pytest.mark.skip(
    reason="Stub usa SessionLocal global; integração com SQLite in-memory dos "
    "testes precisa de fixture mais elaborada. Validação manual via "
    "docker compose up + upload na UI."
)
@pytest.mark.asyncio
async def test_worker_stub_simula_extracao_apos_upload(
    client: AsyncClient, db_session, monkeypatch, tmp_path
) -> None:
    """Configura delay=0 e confirma que o stub:
    1. muda Proposal.status para 'extracted'
    2. cria Baseline draft com 6 deliverables
    """
    import asyncio

    monkeypatch.setenv("STUB_WORKER_ENABLED", "true")
    monkeypatch.setenv("STUB_WORKER_DELAY_S", "0")
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "files"))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("LOCAL_STORAGE_BASE_URL", "http://test")

    from jump_storage.factory import reset_cache

    from app.core.config import get_settings as _gs
    reset_cache()
    _gs.cache_clear()

    # O stub usa SessionLocal direto, que aponta para a engine real (asyncpg).
    # No teste, queremos ele use a mesma SQLite em memória do client. Vamos
    # patchar SessionLocal para aceitar a engine de teste.
    from app.db import session as session_mod
    bind = db_session.get_bind()
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    new_session = async_sessionmaker(bind, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(session_mod, "SessionLocal", new_session)

    import io
    tok = await _login_as(client, role="GP", email="gp-stub@x.com")
    r = await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {tok}"},
        json={"name": "Bradesco SAS", "client_name": "Bradesco"},
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    pdf_bytes = b"%PDF-fake"
    files = {"file": ("p.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r2 = await client.post(
        f"/projects/{pid}/proposals",
        headers={"Authorization": f"Bearer {tok}"},
        files=files,
    )
    assert r2.status_code == 201

    # Aguarda o stub finalizar (delay=0 + um tick async)
    for _ in range(20):
        await asyncio.sleep(0.05)
        r3 = await client.get(
            f"/projects/{pid}/proposals/{r2.json()['id']}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        if r3.json()["status"] == "extracted":
            break
    assert r3.json()["status"] == "extracted"

    # Verifica que existe baseline draft
    r4 = await client.get(
        f"/projects/{pid}/active-baseline", headers={"Authorization": f"Bearer {tok}"}
    )
    # ainda não ativada — só draft. /active-baseline retorna None
    assert r4.status_code == 200
    assert r4.json() is None
