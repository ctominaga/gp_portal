# Arquitetura — Jump GP Portal

## Visão de 1 página

Dois ambientes operam o produto:

```
┌──────────────────────── RAILWAY (cloud, 24/7) ────────────────────────┐
│                                                                       │
│   Frontend (Next.js 14)  ◀─HTTPS─▶  Backend (FastAPI)                 │
│        │                              │   │   │                       │
│        │                              ▼   ▼   ▼                       │
│        │                   Postgres  Redis  R2 (S3)                   │
│        │                              ▲                               │
└────────┼──────────────────────────────┼───────────────────────────────┘
         │ usuários (GP, PMO, CLIENT)   │ jobs publicados em
         │ via internet pública         │ jobs.agent
         │                              ▼
         │            ┌─── MÁQUINA WINDOWS DA JUMP (worker) ────┐
         │            │  Python worker  ──▶  jump-agent-runner   │
         └────────────┤  ▲                       │               │
        SSE / fetch   │  │                       ▼               │
                      │  │ POST /internal/...   WSL2 + tmux       │
                      │  │ (JWT + HMAC)          │   │            │
                      │  │              ┌────────▼   ▼────────┐  │
                      │  │              │ claude -p   codex   │  │
                      │  │              │ (headless ou broker)│  │
                      │  └──────────────┴─────────────────────┘  │
                      └────────────────────────────────────────────┘
```

## Princípios

1. **Zero API keys de LLM em runtime.** A inteligência vem de Claude Code e Codex CLI, ambos invocados a partir de assinaturas corporativas Jump na máquina worker. Headless é prioridade; broker tmux é fallback automático para login expirado / quota / detecção de modo interativo. Engine secundária é tentada se primária falhar.

2. **Resultado de agente só é aceito via arquivo JSON canônico.** Stdout, prosa e sentinel sozinho são inválidos. Garante reprodutibilidade e auditabilidade.

3. **Comunicação Worker → Backend dupla-autenticada.** Cada callback carrega `X-Worker-Token` (segredo compartilhado) + `X-Worker-Signature` (HMAC-SHA256 do body) + `X-Worker-Timestamp` (anti-replay 5 min).

4. **RBAC por role.** GP, PMO, CLIENT, OPERATOR. Cliente só vê reports aprovados do próprio projeto.

5. **Toda execução de IA é registrada em `AgentRunLog`** com engine, rota, tentativas, falhas, duração. Permite auditoria LGPD e tuning de prompts.

6. **Idempotência em endpoints de mutação.** Uploads, submissão de report e callback do worker usam `run_id` como chave.

7. **Logs estruturados em JSON** com `timestamp`, `level`, `request_id`, `user_id`, `event`, `details`. Sentry para erros não tratados.

## Componentes

| Componente | Responsabilidade |
|---|---|
| `frontend/` | UI Next.js 14 — telas de GP, PMO, cliente, operador. SSE para notificações em tempo real. |
| `backend/` | API REST FastAPI, modelo de domínio, autenticação, fila de jobs, callbacks do worker, integração Resend. |
| `jump_agent_runner/` | Biblioteca Python reutilizável que invoca Claude Code e Codex CLI com fallback. Não depende de banco. |
| `worker/` | Processo na máquina Windows da Jump. Consome Redis, baixa input do R2, dispara `AgentRunner`, devolve resultado autenticado. |
| `shared/schemas/` | JSON schemas dos contratos de saída dos agentes (proposal_extraction, report_insights, portfolio_patterns). |

## Fluxos críticos

**Extração de proposta:** GP faz upload → backend salva no R2 e cria `Proposal(status=pending_extraction)` + publica job → worker consome, baixa, invoca `proposal_reader` agente → POST resultado → backend cria `Baseline(status=draft)` + notifica GP.

**Submissão de report:** GP preenche wizard → backend salva → publica job `report_analyzer` → worker processa → backend salva `AIInsight`s → notifica PMO. PMO aprova → cliente é notificado.

**Análise de portfólio (diária):** scheduler publica job `portfolio_pattern_analysis` → worker anonimiza e processa → insights salvos com `scope=portfolio`.

## O que ainda não está construído (F0)

Apenas scaffolding e infra local. Modelo de domínio, agentes e UIs entram nas Fases 1 a 5.
