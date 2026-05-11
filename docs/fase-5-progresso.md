# Fase 5 — Progresso

**Status atual:** F5.1 fechada. F5.2 a F5.9 pendentes. Pronto para retomada.

**Última atualização:** 2026-05-11

---

## F5.1 — Schemas P2 ✅ FECHADA

Alinhamento dos 4 modelos (Risk, ActionPlan, Deliverable, PendingItem) à spec v3.1 §4.2 + ao prompt `proposal_reader_v1.md`. Estratégia: drop+recreate onde havia divergência de enum (COUNT=0 já investigado em ETAPA 2A da sub-fase Risk; sem dados em produção).

### Commits

| # | Commit | Modelo | Migration |
|---|---|---|---|
| 1 | `e888415` | **Risk** — probability+impact com level derivado; RiskStatus 4 valores; OPEN_RISK_STATUSES; mitigation_plan | `0010_risk_p_i_level` |
| 2 | `edaec34` | **ActionPlan** — objective + linked_risk_id + linked_deliverable_id (ON DELETE SET NULL); expansão linked_*_description/title em lote | `0011_actionplan_objective_links` |
| 3 | `1284bc5` | **Deliverable** — type+acceptance_criteria+dependencies+status; complexity 3→5 PT-BR; category String→enum; cross-model auto-update CONCLUDED | `0012_deliverable_type_acceptance_deps_status` |
| 4 | `7263526` | **PendingItem** — impact (nullable) + created_at (cumpre open_date semanticamente) | `0013_pendingitem_impact_created` |

### Métricas (evolução durante F5.1)

| Métrica | Início | Risk | ActionPlan | Deliverable | **PendingItem (final)** |
|---|---|---|---|---|---|
| pytest backend | 93 | 105 | 111 | 116 | **119** |
| Cobertura backend | 71.33% | 72.62% | 72.45% | 72.71% | **72.76%** |
| vitest frontend | 69 | 69 | 72 | 73 | **76** |

### Conformidade — itens marcados em `docs/conformidade-v3.1.md`

- ~~F. Risk: probability/impact + mitigation_plan~~ → endereçado em `e888415`
- ~~G. ActionPlan: objective + vinculações~~ → endereçado em `edaec34`
- ~~H. Deliverable: type + acceptance + dependencies + status~~ → endereçado em `1284bc5`
- ~~J. PendingItem: impact + open_date~~ → endereçado em `7263526`

---

## F5.2 a F5.9 — Pendentes

Conforme plano em `docs/fase-5-plano.md`. Ordem recomendada (conservadora: schemas estáveis antes de LGPD/deploy):

| # | Sub-fase | Estimativa | Bloqueia / é bloqueada por |
|---|---|---|---|
| F5.2 | Versionamento de escopo (ScopeChange + fluxo aprovação PMO) | ~25k | livre — caminho crítico para deploy completo |
| F5.3 | Retrospectiva (`POST /projects/{id}/close` + 4 campos + UI) | ~30k | bloqueia F5.5 (agente portfólio usa retrospectivas) |
| F5.4 | Modo de Report Assistido por IA | ~25k | livre |
| F5.5 | Agente de Inteligência Cruzada (heurística inicial + flag) | ~30k | depende de F5.3 |
| F5.6 | WSL clean + F2.6 worker real + F2.8 smoke | ~50k (teto) | depende de runbook + execução manual sua |
| F5.7 | LGPD: `lgpd.md` + `/me/data-export` + `/me/data-deletion-request` | ~45k | depende de F5.1 estabilizado (✅) + F5.3 (idealmente) |
| F5.8 | Exportação PDF/PPTX | ~50k (teto) | livre |
| F5.9 | Deploy Railway + v3.2 consolidada | ~40k | depende de F5.6 (worker real para piloto) + F5.7 (LGPD assinado) |

---

## Decisões respondidas (3 de 8 do plano F5)

| # | Pergunta | Resposta |
|---|---|---|
| **#1** | F5.5 antes ou depois do piloto rodar? | **Construir infra agora, ativar UI quando 5+ projetos encerrados.** Implementação: flag `portfolio_intelligence_enabled` em `PortfolioConfig` (default false). Backend produz insights independente da flag (alimenta histórico). UI mostra card aguardando volume mínimo + contagem; quando flag=true, exibe insights reais. Gatilho via `PATCH /portfolio/config`. |
| **#2** | F5.6 WSL setup — Christopher instala ou runbook? | **Runbook.** Quando F5.6 chegar, eu produzo `docs/runbooks/setup-worker-wsl.md` detalhado (pré-requisitos máquina, WSL2 Ubuntu, instalação `claude`/`codex` no Linux puro, login interativo passo a passo, tmux com persistência, smoke test após cada passo). Christopher executa manualmente. |
| **#7** | F5.1 — F.Risk: drop+recreate ou backfill heurístico? | **Drop+recreate.** Investigação confirmou COUNT(*) FROM risks = 0 (mesma máquina, mesmo banco in-memory, ambiente pré-piloto). Estratégia replicada para Deliverable enums (D1+D2) também sem cerimônia. |

---

## Decisões pendentes (5 de 8) — pedir antes de cada sub-fase relacionada

| # | Pergunta | Quando vou perguntar |
|---|---|---|
| **#3** | F5.7 LGPD — texto jurídico revisado por advogado externo? Christopher é DPO designado; posso produzir documento técnico (RAT, RPS, retenção), mas linguagem contratual pode exigir revisão. | Antes de iniciar F5.7 |
| **#4** | F5.8 — PDF e PPTX ambos, ou só PDF inicialmente? PPTX exige mais código (`python-pptx` mais arestas que `reportlab`). PDF cobre 80% dos casos. | Antes de iniciar F5.8 |
| **#5** | F5.9 — deploy beta no Railway com dados seed ou esperar piloto real autorizar? Bradesco tem requisitos próprios (LGPD assinado, contratos de tratamento). | Antes de iniciar F5.9 |
| **#6** | F5.X (P3 hardening) — dentro de F5 ou postergar para F6? A spec v3.1 §10 (Plano em fases) coloca esses itens em F6. | Quando decidir entre fechar F5 ou ampliar |
| **#8** | F5.6 — engine primário do worker real continua Claude ou aposta em Codex inicialmente? Smoke F2.8 vai decidir, mas pode haver preferência de operação. | Antes de iniciar F5.6 |

---

## Débitos acumulados — links para contexto

### Débito K — F2.8 smoke real do agente leitor adiado

**Onde:** `docs/decisoes.md` (ADR 2026-05-11 — "F2.8 adiado para F5") + tabela em `docs/conformidade-v3.1.md`
**Motivo:** `claude` CLI v2.1.138 instalado no Windows e acessado via mount WSL errático em modo headless após login interativo
**Plano:** absorvido em F5.6 (WSL clean + F2.6 + F2.8 num pacote por compartilhar pré-requisito)

### Débito L — v3.1 §6.4.1 desatualizada

**Onde:** `docs/decisoes.md` (Adendo do ADR 2026-05-11) + `docs/conformidade-v3.1.md` (linha do schema ProposalExtraction)
**Motivo:** enums do schema/prompt v1 divergiram do que a spec §6.4.1 listava. Prompt vence (fonte), spec será atualizada
**Plano:** gerar v3.2 consolidada em F5.9 com diff explícito do que mudou (regra de governança ADR 2026-05-08)

### Débitos menores P3 do F5.1

Todos em `docs/conformidade-v3.1.md` seção "Débitos menores de F5.1 (P3)":

| ID | Item | Onde aparece |
|---|---|---|
| **F5.1.a** | `open_critical` em Python (não SQL) por causa de property `Risk.level` | `app/api/v1/portfolio.py` linhas ~94-101 |
| **F5.1.b** | `Severity` (frontend) + `RiskLevel` (backend) coexistem com mesmos 4 valores | `frontend/src/lib/types.ts` linha 103 + `backend/app/models/domain.py` classe RiskLevel |
| **F5.1.c** | Vitest não renderiza shadcn `<TabsContent>` em jsdom isolado | Tentativa removida em `e888415`; compensado por shape tests puros |

---

## Estado do repo (HEAD)

```
7263526 feat(backend,frontend): F5.1 PendingItem com impact+open_date v3.1 §4.2.5
1284bc5 feat(backend,frontend): F5.1 Deliverable com type+acceptance+dependencies+status v3.1 §4.2.2
edaec34 feat(backend,frontend): F5.1 ActionPlan com objective+vinculacoes v3.1 §4.2.4
e888415 feat(backend,frontend): F5.1 Risk com probability+impact+level+status v3.1 §4.2.3
f9c3fce docs: plano de F5 com 9 sub-fases e ~390k tokens estimados
bc32d04 fix(backend): alinhar SOURCE_EXCERPT_MAX ao prompt v1 R4
9824b96 docs: fase-4-relatorio.md final
[...]
```

---

*Documento atualizado ao fim de cada sub-fase de F5 fechada. Próximo update: ao fim de F5.2.*
