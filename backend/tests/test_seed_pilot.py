"""F5.9a Commit 3 — seed_pilot.py idempotente.

2 cenários:
  1. Rodar uma vez cria 3 users com roles distintos.
  2. Rodar duas vezes não duplica (idempotente — no-op no segundo run).

O script usa `SessionLocal` global; o conftest sobrescreve `get_db` para
o ASGI app, mas o `SessionLocal` ainda aponta para a engine de prod.
Aqui rodamos o seed contra o `db_session` do conftest diretamente,
chamando `_seed_one` em vez de `run_seed()`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.user import Role, User
from scripts.seed_pilot import _SEED_USERS, _seed_one


@pytest.mark.asyncio
async def test_seed_cria_3_users_com_roles_distintos(
    db_session, monkeypatch
) -> None:
    monkeypatch.setenv("SEED_PMO_PASSWORD", "JumpDev123!")
    monkeypatch.setenv("SEED_GP_PASSWORD", "JumpDev123!")
    monkeypatch.setenv("SEED_CLIENT_PASSWORD", "JumpDev123!")

    results = []
    for spec in _SEED_USERS:
        results.append(await _seed_one(db_session, spec))
    await db_session.commit()

    assert all(r["action"] == "created" for r in results)
    rows = list(
        (await db_session.execute(select(User).order_by(User.email)))
        .scalars().all()
    )
    assert len(rows) == 3
    roles = {u.role for u in rows}
    assert roles == {Role.PMO, Role.GP, Role.CLIENT}
    emails = {u.email for u in rows}
    assert emails == {
        "pmo@jumplabel.com.br",
        "gp.bradesco@jumplabel.com.br",
        "cliente@bradesco-dev.local",
    }


@pytest.mark.asyncio
async def test_seed_eh_idempotente_segundo_run_nao_duplica(
    db_session, monkeypatch
) -> None:
    monkeypatch.setenv("SEED_PMO_PASSWORD", "JumpDev123!")
    monkeypatch.setenv("SEED_GP_PASSWORD", "JumpDev123!")
    monkeypatch.setenv("SEED_CLIENT_PASSWORD", "JumpDev123!")

    # Primeira execução: 3 criados.
    for spec in _SEED_USERS:
        r = await _seed_one(db_session, spec)
        assert r["action"] == "created"
    await db_session.commit()

    # Segunda execução: 3 rehashed (env vars setadas), total no banco
    # continua 3. Idempotente em termos de quantidade de usuários — a
    # ação "rehashed" atualiza o password_hash mas não duplica o registro.
    # Se as env vars estivessem vazias, retornaria "skipped" sem tocar
    # no hash (path coberto em test_seed_skipa_quando_user_existe_sem_env).
    for spec in _SEED_USERS:
        r = await _seed_one(db_session, spec)
        assert r["action"] == "rehashed"
        assert "password updated" in r["reason"]
    await db_session.commit()

    rows = list(
        (await db_session.execute(select(User))).scalars().all()
    )
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_seed_gera_password_random_quando_env_vazio(
    db_session, monkeypatch
) -> None:
    """Se SEED_*_PASSWORD vazio, _seed_one gera senha random e devolve no
    payload — operador anota do log."""
    monkeypatch.delenv("SEED_PMO_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_GP_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_CLIENT_PASSWORD", raising=False)

    spec = _SEED_USERS[0]
    r = await _seed_one(db_session, spec)
    assert r["password_generated"] is True
    assert r["password_to_record"] is not None
    assert len(r["password_to_record"]) >= 24
