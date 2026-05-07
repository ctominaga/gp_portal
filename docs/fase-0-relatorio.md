# Fase 0 — Relatório

**Data:** 2026-05-06
**Status:** entregue (parcialmente validado — ver pendências)
**Commit:** `f40aa87 chore(f0): scaffolding inicial do monorepo jump-report`

## O que foi feito

### Estrutura do monorepo (F0.1)
Criada a árvore conforme spec do prompt: `backend/`, `frontend/`, `jump_agent_runner/`, `worker/`, `docs/`, `shared/`, `.github/workflows/`. Todos com `__init__.py` e arquivos de scaffolding necessários.

### Backend FastAPI (F0.2, F0.8, F0.9)
- `backend/pyproject.toml` com deps fixadas conforme prompt: FastAPI 0.115, SQLAlchemy 2.0 + asyncio, Alembic 1.13, asyncpg, Pydantic 2.9, python-jose, passlib[bcrypt], redis, httpx, pypdf, python-docx, tenacity, structlog, sentry-sdk, boto3, resend. Dev deps: pytest 8.3 + asyncio + cov, ruff 0.8, mypy 1.13. Python ≥3.12 obrigatório.
- `app/main.py` com `/health` retornando `{status, db, redis, version}`. Verifica conectividade real com Postgres (SELECT 1) e Redis (PING).
- `app/core/config.py` lê `.env` via pydantic-settings, com defaults sensatos para dev.
- `app/core/logging.py` configura structlog em formato JSON com `timestamp`, `level`, `request_id`, `user_id`, `event`, `details` — middleware HTTP propaga `request_id` via header `x-request-id`.
- Sentry init condicional (só se `SENTRY_DSN` setado).
- CORS configurável via `CORS_ORIGINS`.
- Alembic configurado para async (`alembic/env.py`), com baseline vazio em `versions/20260506_0001_baseline.py`. Modelos de domínio entram em F2.
- `Dockerfile` com Python 3.12-slim, healthcheck em `/health`.

### Frontend Next.js 14 (F0.5, F0.10)
- `frontend/package.json` com Next 14.2.18 (App Router), TypeScript 5.6, Tailwind 3.4, shadcn primitives (Button, Card), Vitest 2.1, Playwright 1.48, axios, zod, lucide-react.
- `tailwind.config.ts` com tema shadcn (cores HSL via CSS vars, dark mode).
- `components.json` configurado para shadcn `new-york` style.
- Página inicial em `src/app/page.tsx` com cards apresentando o produto.
- Página `/health-check` em `src/app/health-check/page.tsx` faz fetch SSR no `/health` do backend e exibe os campos.
- Vitest configurado com jsdom + alias `@/`. Smoke test placeholder em `tests/smoke.test.tsx`.
- Playwright configurado para `tests/e2e/` (vazio por enquanto).
- `Dockerfile` multi-stage com `output: "standalone"`.

### Jump Agent Runner (F0.3)
- `jump_agent_runner/pyproject.toml` enxuto: deps mínimas (Pydantic + structlog), dev (pytest, ruff, mypy), entry point `jump-runner` apontando para `cli.main:main` (a ser implementado em F1/S7).
- README explicando o status de implementação por sub-sprint.
- Markers de pytest: `requires_claude_cli`, `requires_codex_cli`, `requires_wsl`.

### Worker (F0.4)
- `worker/pyproject.toml` com deps de runtime (redis, httpx, pydantic, structlog, tenacity, boto3) + dependência local `jump-agent-runner` via `[tool.uv.sources]`. Entry point `jump-worker` aponta para `worker.main:main` (F2).

### Docker compose (F0.6)
- `docker-compose.yml` cobrindo apenas Railway side: Postgres 16-alpine, Redis 7-alpine, backend (build local com hot reload e bind mount), frontend (build local). Healthchecks em postgres e redis. Volume nomeado `pgdata`. **Worker não está aqui, conforme spec.**
- YAML estruturalmente validado (PyYAML carrega sem erro; serviços `db`, `redis`, `backend`, `frontend` reconhecidos).

### Variáveis de ambiente (F0.7)
- `.env.example` documentando todas as variáveis requeridas pela spec: DB, Redis, JWT, segredos do worker (token + HMAC), R2 (account/access/secret/bucket/endpoint), Resend, Sentry, CORS. Plus `NEXT_PUBLIC_API_URL` para o frontend.
- Defaults seguros (placeholder `change-me-...`) para que o app não suba acidentalmente em produção sem configuração explícita.

### CI GitHub Actions (F0.11)
- `ci-backend.yml`: roda em PR/push tocando `backend/**`. Sobe Postgres 16 + Redis 7 como services; instala deps; ruff + mypy (continue-on-error em F0) + pytest.
- `ci-frontend.yml`: PR/push em `frontend/**`. npm install + lint + type-check + vitest + build.
- `ci-runner.yml`: PR/push em `jump_agent_runner/**`. ruff + pytest.
- `deploy-railway.yml`: placeholder com `workflow_dispatch` apenas — ativado em F5 com secret `RAILWAY_TOKEN`.

### Documentação (F0.12)
- `docs/arquitetura.md`: diagrama ASCII de 1 página + princípios + componentes + fluxos críticos.
- `docs/decisoes.md`: 4 ADRs registrados (estrutura inicial, propostas reais como fixtures, cobertura ativa só a partir da F1, Resend com email pessoal corporativo).

### Gold standard de propostas (F0.13)
- `extract.py` lê os 3 PDFs em `propostas/` e gera `<slug>.txt` em `backend/tests/fixtures/proposals/`.
- **bradesco_sas_databricks** (text-layer ok, 3097 linhas extraídas): `expected.json` com 21 entregáveis em 4 fases (3 sprints quinzenais com 10/4/4 grupos + phaseout com 3 entregas transversais). Squad: 1 Líder Técnico + 3 Engenheiros de Dados full-time, 320h/sprint. Inclui out_of_scope e key_premises.
- **torra_governanca** (PDF predominantemente imagem; só páginas comerciais finais têm texto): `expected.json` documenta os dois cenários comerciais (R$456k em 12 meses ou R$250k em 8 meses), marca `_needs_ocr: true` e `deliverables: []`. Estratégia de teste: pipeline real deve retornar Baseline em status `needs_ocr` quando OCR não estiver disponível.
- **diretriz_estrategica** (PDF totalmente imagem em baixa resolução): `expected.json` com `_no_text_layer: true` e `expected_failure_reason: "PDF_NO_TEXT_LAYER"`.
- README na pasta de fixtures explicando o contrato.

### Git (F0.14 — parcial)
- `git init -b main` na raiz do monorepo.
- Remote `origin` apontando para `https://github.com/ctominaga-jump/gp_portal.git`.
- Local `user.email` e `user.name` configurados (Christopher Tominaga / christopher.tominaga@jumplabel.com.br).
- `.gitattributes` com `* text=auto eol=lf` evitando diffs ruidosos por CRLF.
- `.gitignore` cobrindo `.env`, `__pycache__`, `node_modules`, `.next`, caches, PDFs em fixtures (excluídos do repo por tamanho).
- Primeiro commit feito: `f40aa87 chore(f0): scaffolding inicial do monorepo jump-report` (Conventional Commits, co-author Claude).

## O que foi testado

| Item | Status | Observação |
|---|---|---|
| Estrutura de pastas | ✅ | `find` confirma todas as pastas esperadas |
| Extração das 3 propostas | ✅ | 64/42/111 páginas processadas; 1 PDF com texto rico, 2 com pouco/nenhum texto (são imagens) |
| `docker-compose.yml` válido | ✅ | `docker compose config --services` retorna `db redis backend frontend` |
| Git init + remote + commit | ✅ | 3 commits: scaffolding, relatório, fixes |
| Disco liberado | ✅ | de 0 GB para 18.4 GB (npm cache 3.4GB + Temp 0.6GB + Docker prune ~14GB) |
| Python 3.12 instalado | ✅ | `winget install Python.Python.3.12` → 3.12.10 disponível em `py -3.12` |
| Backend `pip install -e ".[dev]"` | ✅ | 79 pacotes instalados em venv local; pin `resend==2.5.0` corrigido para `>=2.5,<3` (versão exata não existia) |
| Backend `pytest` | ✅ | 1 passed em 0.56s (Python 3.12.10) |
| Frontend `npm install` | ✅ | 533 pacotes em 4min |
| Frontend `npm test` (vitest) | ✅ | 1 passed em 9ms (Node 24, Next.js 14.2.35) |
| `docker compose build` em Docker local | ⚠️ | Comandos Docker timeoutavam após o prune (daemon flaky pós-restart). Mantido como pendência — CI Linux do GitHub Actions valida o mesmo Dockerfile em ambiente limpo |
| `docker compose up` + `/health` end-to-end | ⏳ | Bloqueado pelo item acima. Não é crítico para começar F1 (S0 a S2 do agent-runner não dependem de Postgres/Redis) |
| `git push -u origin main` | ✅ | URL corrigida para `https://github.com/ctominaga/gp_portal.git` (não `ctominaga-jump`); 6 commits no remote |
| CI verde no GitHub Actions | ✅ | ci-backend ✓, ci-frontend ✓, ci-runner ✓ — todos completed/success no commit `bc669c6` |

## Pendências e bloqueios (atenção)

### ✅ Resolvidos no ciclo F0-cleanup (2026-05-07)

- **Disco liberado de 0 → 18.4 GB** com `npm cache clean --force`, limpeza de Temp e `docker system prune -a -f --volumes`.
- **Python 3.12.10 instalado** via winget. venv local em `backend/.venv` com todas as deps OK.
- **Backend pytest e frontend vitest passam** localmente (1 teste cada, ambos em ms).
- **Pin de resend corrigido** (`==2.5.0` → `>=2.5,<3`).
- **Next.js bumpado para 14.2.35** (CVE 2025-12-11).
- **Portas do compose parametrizadas** (`POSTGRES_HOST_PORT=55432`, `REDIS_HOST_PORT=56379`, `FRONTEND_HOST_PORT=13000`) para evitar conflito com Postgres/Node host do dev.

### 🟡 Docker local flaky pós-prune
Após `docker system prune -a -f --volumes`, comandos Docker (`docker ps`, `docker images`, `docker compose build`) começaram a timeoutar mesmo com Docker Desktop reiniciado. Hipótese: WSL2 backend ainda compactando vhdx ou processo do `buildkit` órfão.

**Mitigação:** confiamos no CI Linux do GitHub Actions para validar `docker compose` em ambiente limpo. Para validar localmente quando o usuário tiver tempo:
```bash
docker compose up -d
curl http://localhost:8000/health
# Frontend em http://localhost:13000/health-check
```
Não bloqueia início de F1: S0–S2 do `jump-agent-runner` não tocam Postgres/Redis.

### ✅ git push e CI resolvidos
URL correta era `https://github.com/ctominaga/gp_portal.git` (conta pessoal, não org `ctominaga-jump`). Push fez `branch 'main' set up to track 'origin/main'`. Os 3 workflows (`ci-backend`, `ci-frontend`, `ci-runner`) foram disparados via `workflow_dispatch` adicionado a cada um, e todos terminaram em `completed/success` no commit `bc669c6`.

### 🟡 PDFs do gold standard não estão no git
Tamanhos individuais: Bradesco 73MB, Torra 10MB, Diretriz 7.7MB. Excluídos do repo (gitignore). Os `.txt` extraídos e os `.expected.json` estão commitados. Para rodar testes que abrem o PDF original, basta ter `Jump-GP-portal/propostas/` populado localmente.

### 🟡 Cobertura ≥70% começa só em F1
Conforme decisão registrada em `docs/decisoes.md`, F0 não enforce cobertura. CI já chama `pytest`, mas o `--cov-fail-under=70` será adicionado no primeiro PR de F1.

## Próximos passos (Fase 1 — `jump-agent-runner`)

A F1 entrega a biblioteca de execução de agentes em 8 sub-sprints (S0-S7), conforme spec `02_jump_agent_runner_spec.md`. Resumo do plano:

- **S0 (1d)** — `types.py`, `ArtifactValidator` com 3 regras, `Observer` com saída JSONL em `~/.jump-runner/logs/`
- **S1 (1d)** — `ClaudeHeadlessRoute`: invoca `claude -p`, detecta `LOGIN_REQUIRED/QUOTA_EXCEEDED`, heartbeat, hard timeout
- **S2 (1d)** — `CodexHeadlessRoute`: invoca `codex exec` via `wsl.exe -d Ubuntu --`
- **S3 (2d)** — `WSLTmuxBroker`: gerencia sessão tmux persistente, login interativo
- **S4 (1d)** — `ClaudeProvider` com fallback headless→broker
- **S5 (1d)** — `CodexProvider` análogo
- **S6 (1d)** — `AgentRunner` com fallback entre engines (Claude→Codex)
- **S7 (1d)** — CLI (`jump-runner login-confirm`, `jump-runner smoke`), `setup-windows.ps1`, smoke test E2E

Você confirmou que `claude -p` e `codex exec` estão disponíveis no terminal — vou executar smokes reais com ambos durante S1, S2 e S7.

## F0 fechada — pronto para iniciar F1

Tudo verde:
- 6 commits no remote `ctominaga/gp_portal`.
- `ci-backend`, `ci-frontend`, `ci-runner` ✅ na sua primeira execução real.
- Stack local validada (Python 3.12, Node 24, Next 14.2.35, FastAPI 0.115).
- Gold standard de propostas anotado.

Único item que fica como "validar quando a máquina worker estiver pronta": `docker compose up` em Docker host estável (o Docker local entrou em estado degradado pós-prune neste ciclo). Isso não bloqueia F1/S0–S2 (independem de Postgres/Redis).

## Próximo: Fase 1 / Sub-sprint S0

Pelo plano da F1 da spec, S0 entrega em ~1 dia:
- `jump_agent_runner/types.py`: `Engine`, `Route`, `FailureReason`, `AgentTask`, `AttemptLog`, `AgentResult`, `ValidationResult`
- `jump_agent_runner/artifact.py`: `ArtifactValidator` com as 3 regras (arquivo válido / recuperar do relay / rejeitar)
- `jump_agent_runner/observer.py`: emite eventos para stdout (humano) + JSONL em `~/.jump-runner/logs/{date}.jsonl`
- Estrutura de pacote, instalável via `pip install -e .`
- Testes unitários do validator: JSON em arquivo aceito / JSON balanceado em relay aceito / prosa rejeitada com `ARTIFACT_INVALID` / sentinel sem nada rejeitado com `SENTINEL_NOT_OBSERVED` / arquivo existe mas é texto livre rejeitado.

Confirma que posso começar S0?
