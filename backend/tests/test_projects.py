"""Testes do CRUD de Projects + upload de Proposals."""
from __future__ import annotations

import io
from pathlib import Path

import jump_storage.factory as storage_factory
import pytest
from httpx import AsyncClient
from jump_storage import LocalStorage
from jump_storage.factory import reset_cache


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Substitui o storage por LocalStorage em tmp_path para cada teste."""
    from app.core.config import get_settings as _get_settings

    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "files"))
    monkeypatch.setenv("JWT_SECRET", "ci-secret-change-me")
    monkeypatch.setenv("LOCAL_STORAGE_BASE_URL", "http://test")
    reset_cache()
    _get_settings.cache_clear()  # força releitura do JWT_SECRET
    yield
    reset_cache()
    _get_settings.cache_clear()


async def _login_as(client: AsyncClient, *, role: str, email: str) -> str:
    await client.post(
        "/auth/register",
        json={"name": role.title(), "email": email, "password": "JumpDev123!", "role": role},
    )
    r = await client.post("/auth/login", json={"email": email, "password": "JumpDev123!"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_project_como_gp(client: AsyncClient) -> None:
    tok = await _login_as(client, role="GP", email="gp1@x.com")
    r = await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "name": "Bradesco SAS->Databricks",
            "client_name": "Bradesco",
            "description": "migração",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Bradesco SAS->Databricks"
    assert body["client_name"] == "Bradesco"
    assert body["client_user_id"] is None


@pytest.mark.asyncio
async def test_create_project_com_client_user_email(client: AsyncClient) -> None:
    await _login_as(client, role="CLIENT", email="cliente@bradesco.com.br")
    tok = await _login_as(client, role="GP", email="gp2@x.com")

    r = await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "name": "Projeto Bradesco",
            "client_name": "Bradesco",
            "client_user_email": "cliente@bradesco.com.br",
        },
    )
    assert r.status_code == 201
    assert r.json()["client_user_id"] is not None


@pytest.mark.asyncio
async def test_create_project_com_email_invalido_falha(client: AsyncClient) -> None:
    tok = await _login_as(client, role="GP", email="gp3@x.com")
    r = await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "name": "Projeto",
            "client_name": "Cliente",
            "client_user_email": "naoexiste@y.com",
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_projects_gp_so_ve_propios(client: AsyncClient) -> None:
    gp1 = await _login_as(client, role="GP", email="gp4@x.com")
    gp2 = await _login_as(client, role="GP", email="gp5@x.com")

    await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {gp1}"},
        json={"name": "P-gp1", "client_name": "C1"},
    )
    await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {gp2}"},
        json={"name": "P-gp2", "client_name": "C2"},
    )

    r = await client.get("/projects", headers={"Authorization": f"Bearer {gp1}"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "P-gp1"


@pytest.mark.asyncio
async def test_get_project_client_so_ve_propio(client: AsyncClient) -> None:
    cl = await _login_as(client, role="CLIENT", email="cl@bradesco.com.br")
    gp = await _login_as(client, role="GP", email="gp6@x.com")

    # Project do GP, sem associação ao cliente
    r = await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {gp}"},
        json={"name": "Projeto", "client_name": "Cliente"},
    )
    pid = r.json()["id"]

    # Cliente sem associação não pode ver
    r2 = await client.get(f"/projects/{pid}", headers={"Authorization": f"Bearer {cl}"})
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_upload_proposal_como_gp_e_proposta_v1(
    client: AsyncClient, tmp_path: Path
) -> None:
    tok = await _login_as(client, role="GP", email="gp7@x.com")
    r = await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {tok}"},
        json={"name": "Bradesco", "client_name": "Bradesco"},
    )
    pid = r.json()["id"]

    pdf_bytes = b"%PDF-fake-content-for-test"
    files = {"file": ("proposta.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r2 = await client.post(
        f"/projects/{pid}/proposals",
        headers={"Authorization": f"Bearer {tok}"},
        files=files,
    )
    assert r2.status_code == 201, r2.text
    body = r2.json()
    assert body["version"] == 1
    assert body["status"] == "pending_extraction"
    assert body["size_bytes"] == len(pdf_bytes)
    assert body["original_filename"] == "proposta.pdf"

    # Upload de v2 incrementa version
    r3 = await client.post(
        f"/projects/{pid}/proposals",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": ("v2.pdf", io.BytesIO(b"%PDF-v2"), "application/pdf")},
    )
    assert r3.status_code == 201
    assert r3.json()["version"] == 2


@pytest.mark.asyncio
async def test_upload_proposal_arquivo_vazio_400(client: AsyncClient) -> None:
    tok = await _login_as(client, role="GP", email="gp8@x.com")
    r = await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {tok}"},
        json={"name": "Projeto", "client_name": "Cliente"},
    )
    pid = r.json()["id"]

    r2 = await client.post(
        f"/projects/{pid}/proposals",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": ("vazio.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_upload_proposal_outro_gp_403(client: AsyncClient) -> None:
    gp1 = await _login_as(client, role="GP", email="gp9@x.com")
    gp2 = await _login_as(client, role="GP", email="gp10@x.com")
    r = await client.post(
        "/projects",
        headers={"Authorization": f"Bearer {gp1}"},
        json={"name": "Projeto", "client_name": "Cliente"},
    )
    pid = r.json()["id"]

    r2 = await client.post(
        f"/projects/{pid}/proposals",
        headers={"Authorization": f"Bearer {gp2}"},
        files={"file": ("p.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_signed_file_route_serve_arquivo_e_rejeita_assinatura_ruim(
    client: AsyncClient, tmp_path: Path
) -> None:
    storage: LocalStorage = storage_factory.get_storage()  # type: ignore[assignment]
    assert isinstance(storage, LocalStorage)
    storage.put(b"hello-world", "x/file.bin")
    url = storage.get_signed_url("x/file.bin", ttl_seconds=60)

    # url tem schema://test/files/signed/<token>/<exp>/<key>
    rel = url.replace("http://test", "")
    r = await client.get(rel)
    assert r.status_code == 200
    assert r.content == b"hello-world"

    # Mesmo path mas token errado → 403
    parts = rel.split("/")
    parts[3] = "0" * 64  # token bogus
    bad = "/".join(parts)
    r2 = await client.get(bad)
    assert r2.status_code == 403
