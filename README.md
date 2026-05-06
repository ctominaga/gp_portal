# Jump GP Portal — Sistema de Report e Gestão Estratégica de Projetos

Produto interno da Jump Label para gestão de reports executivos, baselines de propostas, riscos, planos de ação e portal de cliente. Construído com inteligência via CLIs (Claude Code + Codex CLI) executados em máquina worker dedicada.

## Arquitetura

Dois ambientes interligados:

1. **Railway (cloud, 24/7):** frontend Next.js, backend FastAPI, PostgreSQL, Redis. Acesso via internet pública.
2. **Máquina Windows local da Jump:** roda `jump-agent-runner` invocando `claude -p` e `codex exec` em WSL2 + tmux. Puxa jobs de uma fila Redis no Railway e devolve resultados via HTTP autenticado (JWT + HMAC).

Nenhuma API key paga de LLM em runtime — só CLIs com assinaturas corporativas.

## Estrutura

```
jump-report/
├── backend/             # FastAPI, roda em Railway
├── frontend/            # Next.js 14, roda em Railway
├── jump_agent_runner/   # biblioteca Python — execução de agentes
├── worker/              # processo na máquina Windows da Jump
├── docs/
└── shared/
```

## Setup local (Railway side)

```bash
cp .env.example .env
docker compose up -d
curl http://localhost:8000/health   # {"status":"ok","db":"ok","redis":"ok"}
open http://localhost:3000          # Next.js
```

## Documentação

- `docs/arquitetura.md` — visão de 1 página
- `docs/decisoes.md` — registro de decisões técnicas
- `docs/lgpd.md` — adequação LGPD
- `docs/prompts/` — prompts versionados dos agentes de IA
- `docs/fase-N-relatorio.md` — relatórios por fase de construção

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui |
| Backend | Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic |
| Banco | PostgreSQL 16 |
| Fila/cache | Redis |
| Storage | Cloudflare R2 (S3-compatible) |
| Worker | Python 3.12 + asyncio + jump-agent-runner |
| Engines IA | Claude Code (`claude -p`) + Codex CLI (`codex exec`) |
| Broker | WSL2 + tmux |
| Email | Resend |
| Observabilidade | Sentry + structlog (JSON) |
| CI/CD | GitHub Actions → Railway |
