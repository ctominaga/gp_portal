# Runbook — Operação do piloto Bradesco com worker local + Railway prod

**Status:** piloto Bradesco (F5.9). **Última revisão:** 2026-05-15.
**Executor:** Christopher Tominaga.

Decisão F5.6a.Y + F5.9 abertura: o worker (consumidor da fila Redis
`jobs.agent`) continua local na máquina do Christopher (WSL Linux,
Claude CLI nativo via OAuth Team). O Railway hospeda backend + frontend
+ Postgres + Redis; o worker local conecta no Redis Railway via TLS.

Este runbook cobre o que muda na operação do dia-a-dia comparado com
desenvolvimento puramente local.

---

## 1. Arquitetura operacional do piloto

```
  ┌──────────────────────────────┐
  │ Railway "Jump Label" project │
  │                              │
  │  ┌──────────┐  ┌──────────┐  │
  │  │ frontend │  │  backend │  │  ← endpoints HTTPS públicos
  │  │  Next.js │  │  FastAPI │  │
  │  └────┬─────┘  └────┬─────┘  │
  │       │             │        │
  │       │       ┌─────▼────┐   │
  │       │       │ Postgres │   │
  │       │       └──────────┘   │
  │       │       ┌──────────┐   │
  │       │       │  Redis   │◄──┼──── rediss://...
  │       │       └────▲─────┘   │       (TLS)
  └───────┼────────────┼─────────┘       │
          │            │                 │
          ▼            │                 │
       Bradesco       (jobs)             │
       (browser)        │                │
                        │                │
          ┌─────────────┴────────────────┴───┐
          │ Worker LOCAL (WSL do Christopher)│
          │   jump-worker (Python venv)      │
          │   → claude CLI nativo (OAuth)    │
          │   → callback HMAC ao backend     │
          └──────────────────────────────────┘
```

## 2. Variáveis do worker local (`~/.jump-runner/.env.worker`)

```bash
# Redis Railway via TLS
REDIS_URL=rediss://default:<pwd>@<host>.up.railway.app:<port>/0

# Backend Railway prod
BACKEND_URL=https://backend-<hash>.up.railway.app

# Segredos sincronizados com o backend Railway
WORKER_SHARED_SECRET=<mesmo valor do Railway>
WORKER_HMAC_KEY=<mesmo valor do Railway>

# Claude OAuth — credenciais nativas em ~/.claude/.credentials.json
# (já configurado em F5.6a). Não duplicar aqui.
WORKER_ID=local-chris-wsl-1
WORKER_POLL_INTERVAL_S=2.0
```

## 3. Subir o worker

Após `railway up` do backend e confirmação dos healthchecks:

```bash
# Em WSL Ubuntu, no monorepo:
source ~/.jump-runner/.venv-worker/bin/activate
cd ~/path/to/jump-report
set -a; source ~/.jump-runner/.env.worker; set +a
jump-worker
```

O worker faz heartbeat a cada `WORKER_POLL_INTERVAL_S * 5` segundos no
backend (`POST /internal/worker-heartbeat` com HMAC). Confirme em
prod:

```bash
curl https://backend-<hash>.up.railway.app/operator/workers \
  -H "Authorization: Bearer <token PMO>"
# Esperado: lista contém WORKER_ID com last_seen_at recente.
```

## 4. Smoke produção (F5.9b)

```bash
export BACKEND_URL_PROD=https://backend-<hash>.up.railway.app
export PMO_TEST_USER=pmo@jumplabel.com.br
export PMO_TEST_PASSWORD=<SEED_PMO_PASSWORD anotada>

cd jump-report
python scripts/smoke_production.py
# Output JSON em stdout + exit 0 OK / 1 falha
```

O smoke executa: login → cria projeto → upload Proposal → espera worker
processar (gera Baseline DRAFT) → GP ativa baseline → cria Report com
risk/pending → submissão → aprovação PMO → CLIENT_RELEASED → GET
/me/data-export → cleanup.

## 5. Rotação de segredos

Mudar `WORKER_SHARED_SECRET` ou `WORKER_HMAC_KEY` requer ambos os lados:

```bash
# 1. Gerar novo valor (uma única vez)
NEW_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# 2. Atualizar no Railway
railway variables set --service backend WORKER_SHARED_SECRET=$NEW_SECRET

# 3. PARAR o worker local
# (ctrl+c na sessão jump-worker)

# 4. Atualizar ~/.jump-runner/.env.worker no WSL
# Trocar a linha WORKER_SHARED_SECRET=...

# 5. SUBIR o worker novamente
# Backend rejeita callbacks com segredo antigo entre passos 2 e 5 —
# manter janela curta. Jobs em flight que falharem entram em retry.
```

## 6. Como ver logs

Backend Railway (streaming):
```bash
railway logs --service backend
```

Worker local:
```bash
# Worker loga em stdout no terminal onde foi invocado.
# Para tail histórico, redirecionar na inicialização:
jump-worker 2>&1 | tee -a ~/.jump-runner/worker.log
```

Heartbeat e métricas no PMO:
- `/operator/workers` — lista workers ativos, last_seen, queue_depth.
- `/operator/queue-depth` — profundidade atual da fila.
- `/operator/dead-letter` — jobs que falharam após 3 retries.

## 7. Quando o worker cai

Sintomas: PMO vê queue_depth crescendo, jobs `proposal_extraction` ficam
em QUEUED por mais de 5min.

Diagnóstico:
1. Heartbeat antigo? `GET /operator/workers` no PMO.
2. Logs locais (terminal do `jump-worker`): erro de conexão? Auth?
3. Claude OAuth expirou? Re-login: `claude /login` no WSL.

Re-subir o worker resolve a maioria dos casos. Jobs ficam na fila
até serem processados (não há TTL no Redis para `jobs.agent`).

## 8. Plano de contingência — worker offline > 1h

Se Christopher precisar pausar o WSL:
1. Avisar Bradesco que uploads de proposta vão demorar (queue não
   é processada).
2. Submissões de Report continuam funcionando (não dependem do worker).
3. Reativar o worker assim que possível — o lag se recupera.

## 9. Quando promover/trocar os seed users

Após Bradesco autorizar piloto real:

```bash
# 1. Trocar senhas via /admin (logado como PMO seed):
#    Painel admin → Users → editar pmo@jumplabel.com.br → reset password
#    (UI virá em F6; até lá, via API direto)

# 2. Criar users reais via POST /auth/register para cada GP/CLIENT real.

# 3. Desabilitar SEED_ON_STARTUP no Railway:
railway variables set --service backend SEED_ON_STARTUP=false

# 4. (Opcional) Anonimizar os 3 seed users via:
#    POST /admin/data-requests com request_type=deletion + subject_user_id
#    do seed, depois fulfill. Vide docs/lgpd.md §6.4.
```

---

**Próximo passo:** smoke F5.9b validado por Christopher visualmente no
browser antes de F5.9c (spec v3.2 consolidada).
