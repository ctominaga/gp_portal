"""Testes de auth + RBAC."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.api.deps import require_any_role, require_role
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.models.user import Role


def test_hash_e_verify_password() -> None:
    h = hash_password("JumpDev123!")
    assert h.startswith("$2") and h != "JumpDev123!"
    assert verify_password("JumpDev123!", h) is True
    assert verify_password("errado", h) is False


def test_jwt_round_trip() -> None:
    import uuid

    from app.core.security import decode_token

    sub = uuid.uuid4()
    token = create_access_token(sub=sub, role=Role.GP)
    payload = decode_token(token)
    assert payload["sub"] == str(sub)
    assert payload["role"] == "GP"
    assert "exp" in payload and "iat" in payload


# -------- HTTP --------


@pytest.mark.asyncio
async def test_register_login_e_me_completo(client: AsyncClient) -> None:
    # register
    r = await client.post(
        "/auth/register",
        json={
            "name": "Ana",
            "email": "ana@example.com",
            "password": "JumpDev123!",
            "role": "GP",
        },
    )
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == "ana@example.com"
    assert user["role"] == "GP"
    assert "id" in user

    # register duplicado
    r2 = await client.post(
        "/auth/register",
        json={
            "name": "Ana 2",
            "email": "ana@example.com",
            "password": "JumpDev123!",
            "role": "PMO",
        },
    )
    assert r2.status_code == 409

    # login
    r3 = await client.post(
        "/auth/login", json={"email": "ana@example.com", "password": "JumpDev123!"}
    )
    assert r3.status_code == 200, r3.text
    body = r3.json()
    token = body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "GP"

    # me
    r4 = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r4.status_code == 200
    assert r4.json()["email"] == "ana@example.com"


@pytest.mark.asyncio
async def test_login_credenciais_invalidas(client: AsyncClient) -> None:
    r = await client.post("/auth/register", json={
        "name": "Xena", "email": "x@y.com", "password": "JumpDev123!", "role": "PMO",
    })
    assert r.status_code == 201

    r2 = await client.post("/auth/login", json={"email": "x@y.com", "password": "errado!!"})
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_me_sem_token(client: AsyncClient) -> None:
    r = await client.get("/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_com_token_invalido(client: AsyncClient) -> None:
    r = await client.get("/auth/me", headers={"Authorization": "Bearer banana"})
    assert r.status_code == 401


# -------- RBAC --------


@pytest.mark.asyncio
async def test_require_role_permite_role_correto(client: AsyncClient) -> None:
    # registra GP
    await client.post(
        "/auth/register",
        json={"name": "GP", "email": "gp@x.com", "password": "JumpDev123!", "role": "GP"},
    )
    login = await client.post(
        "/auth/login", json={"email": "gp@x.com", "password": "JumpDev123!"}
    )
    token = login.json()["access_token"]

    @app.get("/_test/gp-only")
    async def gp_only(_user=__import__("fastapi").Depends(require_role(Role.GP))):
        return {"ok": True}

    r = await client.get("/_test/gp-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_require_role_proibe_role_errado(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"name": "Cliente", "email": "c@x.com", "password": "JumpDev123!", "role": "CLIENT"},
    )
    login = await client.post(
        "/auth/login", json={"email": "c@x.com", "password": "JumpDev123!"}
    )
    token = login.json()["access_token"]

    @app.get("/_test/operator-only")
    async def operator_only(_user=__import__("fastapi").Depends(require_role(Role.OPERATOR))):
        return {"ok": True}

    r = await client.get(
        "/_test/operator-only", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_require_any_role_aceita_subset(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"name": "PMO", "email": "p@x.com", "password": "JumpDev123!", "role": "PMO"},
    )
    login = await client.post(
        "/auth/login", json={"email": "p@x.com", "password": "JumpDev123!"}
    )
    token = login.json()["access_token"]

    @app.get("/_test/pmo-or-gp")
    async def pmo_or_gp(_user=__import__("fastapi").Depends(require_any_role(Role.PMO, Role.GP))):
        return {"ok": True}

    r = await client.get(
        "/_test/pmo-or-gp", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
