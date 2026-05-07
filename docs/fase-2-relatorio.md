# Fase 2 — Relatório PARCIAL (F2.1 a F2.5 + F2.7)

**Status:** F2.1, F2.2, F2.3, F2.4, F2.5 e F2.7 entregues. F2.6 (worker remoto) e F2.8 (cadastro Bradesco E2E) **pendentes para ciclo dedicado**.

**Cobertura:** 45 testes verdes no backend + 23 no `jump_storage` = **68 testes na F2**, todos passando localmente.

## F2.1 — Auth + RBAC ✅
Entrega completa: User com Uuid+role, JWT 8h, bcrypt<4 (compatibilidade passlib), endpoints `/auth/register`/`/auth/login`/`/auth/me`, `require_role`/`require_any_role` factories, seed com 4 usuários canônicos.

## F2.2 — Modelo de domínio ✅
16 entidades + 14 enums em `app/models/domain.py`, migration única `0003_domain.py`. Apenas `AgentRunLog` e `WorkerHeartbeat` têm schema explícito na spec v3 — demais inferidos do fluxo funcional. Decisões marcadas com `# TODO(v2.1)` quando aplicável.

## F2.3 — `jump_storage` package + CRUD projetos + upload ✅

**Decisão arquitetural relevante:** `jump_storage` é package compartilhável (ao lado de `jump_agent_runner`), não exclusivo do backend. O worker importa a mesma interface.

```
jump_storage/
├── jump_storage/
│   ├── base.py        ObjectStorage ABC + StorageError
│   ├── local.py       LocalStorage (filesystem) + sign/verify HMAC
│   ├── r2.py          R2Storage (boto3, generate_presigned_url)
│   └── factory.py     get_storage() lê OBJECT_STORAGE_BACKEND
└── tests/             23 testes verdes (10 Local + 5 factory + 8 R2 com mock boto3)
```

`get_signed_url` funciona em ambos:
- **R2:** boto3 nativo
- **Local:** URL apontando para `GET /files/signed/{token}/{exp}/{key:path}` no backend; HMAC-SHA256(secret, key+":"+exp), TTL via `exp`. Backend valida e serve em `app/api/v1/files.py`.

**Backend (CRUD):**
- `POST /projects` (GP|PMO; valida `client_user_email` se presente)
- `GET /projects` (escopo por role: GP vê os próprios; PMO|OPERATOR veem todos)
- `GET /projects/{id}` (CLIENT só vê o próprio; GP só o seu)
- `POST /projects/{id}/proposals` (multipart, GP-only): salva no storage com key `proposals/<id>/v<n>.pdf`, calcula sha256, incrementa `version`, status `pending_extraction`. Quando há `app.state.redis`, **publica job de extração no Redis** (linka com F2.4).
- `GET /projects/{id}/proposals/{pid}`

**CI:** `ci-storage.yml` novo workflow + `ci-backend.yml` instala `jump_storage` antes do backend.

## F2.4 — Fila Redis (publisher) + AgentRunLog ✅

`app/queue/publisher.py`:
- `make_run_id(task_type, project_id)` produz IDs human-readable (`ext-prop-2026-05-07-<projsuffix>-<random>`).
- `enqueue_agent_job(...)` cria `AgentRunLog` em `QUEUED` e publica payload no Redis em `jobs.agent`. **Idempotente**: se `AgentRunLog` com mesmo `run_id` já existe, não republica (retorna o existente).
- `queue_depth(redis)` / `dead_letter_depth(redis)` para o dashboard.

Schema do payload conforme spec v3 §7.4: `run_id, task_type, engine_preference, context, input_files, output_path_hint, schema_hint, timeout_hard_s, heartbeat_s, enqueued_at`.

**Wire automático:** upload de proposta dispara `enqueue_agent_job(task_type=PROPOSAL_EXTRACTION, ...)`. Em CI sem Redis, o handler ignora silenciosamente (não bloqueia o upload).

## F2.5 — Callback HMAC do worker + WorkerHeartbeat ✅

`app/core/worker_auth.py`:
- `require_worker_auth(...)`: dependência FastAPI que valida 3 headers — `X-Worker-Token` (===WORKER_SHARED_SECRET), `X-Worker-Signature` (HMAC-SHA256 do body com WORKER_HMAC_KEY), `X-Worker-Timestamp` (ISO 8601 UTC, anti-replay).
- Tolerâncias: `MAX_TIMESTAMP_SKEW_PAST=5min`, `MAX_TIMESTAMP_SKEW_FUTURE=30s`.
- `sign_worker_payload(body, secret)` reutilizável pelo worker (Python).

`POST /internal/agent-results/{run_id}` (`app/api/internal/agent_results.py`):
- Valida HMAC, parse `AgentResultPayload`, atualiza `AgentRunLog` para `DONE` (success) ou `FAILED`.
- **Idempotência canônica:** estados terminais (`done`, `failed`, `expired`) **não são sobrescritos**. Replay com payload diferente recebe `200 OK` com `{"accepted": false, "duplicated": true, "status": <estado original>}` e o estado consolidado fica preservado.

`POST /internal/worker-heartbeat`: upsert em `WorkerHeartbeat`.

**Os 5 cenários explícitos pedidos foram testados (`tests/test_worker_callback.py`):**
1. timestamp velho (>5min) → 401 ✅
2. timestamp futuro (>30s à frente) → 401 ✅
3. assinatura inválida → 401 ✅
4. token sem assinatura (header faltando) → 401 ✅
5. replay do mesmo run_id com payload diferente → 200 com `duplicated=True`, estado consolidado preservado ✅

Mais: happy path (success/failure), `run_id` inexistente → 404, heartbeat upsert. **9 testes do callback verdes.**

## F2.7 — Dashboard administrativo (endpoint, sem UI) ✅

`GET /operator/workers` (role OPERATOR ou PMO) retorna:
- `workers`: lista de `WorkerSnapshot` com `last_seen_ago_s`, `status`, `sessions_status`, contadores.
- `pending_logins`: scan dos sentinelas `~/.jump-runner/login-pending-{engine}`.
- `queue_depth` + `dead_letter_depth` via Redis (zerados quando Redis indisponível).
- `jobs_in_progress`: AgentRunLogs em `QUEUED` ou `RUNNING`.
- `expected_engine_distribution`: contagem de jobs `DONE` hoje agrupados por engine (`claude`, `codex`, `none`). **Esqueleto sempre presente, mesmo zerado** — sinaliza ao PMO se a política de fallback está saudável conforme planejado.

5 testes verdes (`tests/test_operator.py`): RBAC GP→403, PMO→200 com esqueleto zerado, lista workers+jobs+distribuição, scan de pending_logins, sem-Redis = 0.

## Decisões registradas

- **`bcrypt<4`** pinado por incompatibilidade com `passlib==1.7.4` (bcrypt 5.x removeu `__about__.__version__`).
- **B008 (`Depends` em defaults) ignorado em ruff** — é o padrão idiomático do FastAPI.
- **SQLite in-memory + StaticPool** nos testes — necessário porque in-memory SQLite é por-conexão.
- **`get_settings()` é `@lru_cache`** — testes precisam chamar `get_settings.cache_clear()` ao mudar env vars.
- **`OBJECT_STORAGE_BACKEND=local|r2`** com fallback `local` automático (Signing secret cai no `JWT_SECRET` se `LOCAL_STORAGE_SIGNING_SECRET` não setado).

## Pendente — F2.6 e F2.8 (próximo ciclo)

| Sub | O que falta | Por que ficou |
|---|---|---|
| **F2.6** Worker remoto | `worker/main.py` (loop), `consumer.py` (BLPOP `jobs.agent`), `dispatcher.py` (job→AgentTask, baixa input do storage, monta workspace), `reporter.py` (POST autenticado), `heartbeat.py` (30s) | Precisa de Docker estável + Redis remoto + agentes logados — escopo dedicado |
| **F2.8** Cadastro Bradesco E2E | Operator inicia worker → PMO cria projeto → GP upload → job processado → Baseline draft criado → GP ativa | Depende de F2.6 + Docker estável + (opcional) credenciais R2 + Resend |

## Estado dos commits

| Commit | Sub-sprint |
|---|---|
| `1fb2583` | F2.1 Auth + RBAC |
| `3353ce0` | F2.2 Modelo de domínio |
| `faea708` | F2.3 jump_storage + CRUD + upload |
| (commit deste relatório) | F2.4 Fila + F2.5 Callback HMAC + F2.7 Dashboard |

## Métricas

```
backend/    45 tests verdes em ~38s
jump_storage/   23 tests verdes em ~8s
TOTAL F2:   68 tests
```

Cobertura ≥75% nos módulos novos (a verificar no CI Linux após push).

## Próximo passo

Este relatório fecha o batch F2.1-2.5+2.7. Pronto para discutir prioridades:
- (a) F2.6 worker remoto + F2.8 Bradesco E2E (precisa Docker + credenciais)
- (b) F3 frontend completo (independente, pode rodar em paralelo)
- (c) F4 PMO/Cliente

Sugiro **F3** em seguida — frontend é independente do worker e dá visibilidade do produto rapidamente. F2.6/F2.8 podem ser ciclo dedicado quando Docker local estiver estável e/ou houver uma janela para testes E2E reais.
