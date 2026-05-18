"""Alembic env.py — async-aware, lê DATABASE_URL do app.core.config."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base

# Importa modelos para que `target_metadata` os enxergue.
from app.models import *  # noqa: F401,F403

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

# Default do Alembic é `version_num VARCHAR(32)`. Alguns revision IDs do
# projeto ultrapassam (ex: `0015_scope_change_deliverable_code` = 35 chars,
# `0012_deliverable_type_acceptance_deps_status` = 44 chars). Em SQLite o
# excesso é tolerado, em Postgres dispara `StringDataRightTruncationError`
# quando Alembic tenta gravar a revision. Por isso pré-criamos a tabela
# `alembic_version` com `VARCHAR(255)` antes do Alembic verificar — e
# expandimos via `ALTER TABLE` no caso de bancos legados onde a tabela
# já foi criada com o default.


def _ensure_alembic_version_table(connection: Connection) -> None:
    """Garante `alembic_version.version_num` com largura suficiente.

    - Postgres: cria tabela com `VARCHAR(255)` se não existir; expande
      via `ALTER COLUMN` se já existir com tipo menor. Ambas operações
      idempotentes.
    - SQLite e demais: silent skip — SQLite não impõe length em VARCHAR
      e Alembic cria a tabela sem problemas no fluxo padrão.
    """
    if connection.dialect.name != "postgresql":
        return
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS alembic_version ("
            "  version_num VARCHAR(255) NOT NULL, "
            "  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
            ")"
        )
    )
    try:
        connection.execute(
            text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(255)"
            )
        )
    except Exception:
        # Tipo já é >= 255 ou sessão sem permissão de ALTER. Tabela existe
        # e suporta revision IDs longos — sem ação necessária.
        pass


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    _ensure_alembic_version_table(connection)
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
