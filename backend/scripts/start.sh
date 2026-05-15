#!/usr/bin/env bash
###############################################################################
# Backend start.sh — entrypoint do container produção Railway (F5.9a).
#
# Ordem:
#   1. Ajusta DATABASE_URL se vier do Railway Postgres addon sem driver async.
#   2. Roda alembic upgrade head (idempotente — no-op se já em head).
#   3. (Commit 3 adiciona seed condicional aqui.)
#   4. Inicia uvicorn com 2 workers (suficiente para piloto Bradesco; ajustar
#      em F6 baseado em carga real).
###############################################################################
set -euo pipefail

# Railway Postgres addon entrega DATABASE_URL como `postgresql://...` (driver
# psycopg padrão). SQLAlchemy async com asyncpg precisa do schema explícito
# `postgresql+asyncpg://`. Convertemos aqui em vez de no código para que
# alembic (sync, usa psycopg2/asyncpg pela env) e backend (async) vejam o
# valor correto sem branching.
if [[ "${DATABASE_URL:-}" == postgresql://* ]]; then
  export DATABASE_URL="postgresql+asyncpg://${DATABASE_URL#postgresql://}"
fi

echo "[start.sh] alembic upgrade head"
alembic upgrade head

echo "[start.sh] starting uvicorn on port ${PORT:-8000}"
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 2 \
  --proxy-headers \
  --forwarded-allow-ips='*'
