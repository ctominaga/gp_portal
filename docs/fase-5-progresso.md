# Fase 5 — Progresso

**Status atual:** F5.1, F5.2 e F5.3 fechadas. F5.4 a F5.9 pendentes. Pronto para retomada.

**Última atualização:** 2026-05-13

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

## F5.2 — Versionamento de escopo ✅ FECHADA

Fluxo end-to-end de mudança formal de escopo entre versões de proposta
(v(N) → v(N+1)): GP faz upload v2 → worker importa + cria baseline DRAFT +
ScopeChanges PROPOSED via `diff_baselines` → PMO revisa em `/pmo/scope-changes`
ou `/projetos/[id]/diff` e aprova/rejeita a transição inteira (batch).

### Commits

| # | Commit | Conteúdo |
|---|---|---|
| 1 | `cd8fc45` | Modelo ScopeChange refatorado (+baseline_from_id, +baseline_to_id, +change_type, +approved_by_id) + BaselineStatus.REJECTED + migration `0014_scope_change_refactor` com backfill |
| 2 | `1b85e09` | `POST /baselines/{id}/transition` (PMO, batch approve/reject) + gate em activate_baseline para v2+ (GP → 403) + notify_transition_decision + GETs por projeto e detalhe |
| 3 | `886b74c` | `diff_baselines` cobre MODIFIED (added/removed/modified) + idempotência tripla `(baseline_to_id, change_type, deliverable_code)` + migration `0015_scope_change_deliverable_code` |
| 4 | `c92b076` | Frontend: rota `/pmo/scope-changes`, faixa PMO + modais em `/diff`, badge no portfolio, GET portfólio-wide, `pending_transitions_count`, types TS, vitest |
| 5 | (este commit) | Testes pytest dos endpoints de commit 4 + validação Pydantic do reject + Playwright + dev_notes + conformidade |

### Métricas (evolução durante F5.2)

| Métrica | Início F5.2 | Commit 1 | Commit 2 | Commit 3 | Commit 4 | **Commit 5 (final)** |
|---|---|---|---|---|---|---|
| pytest backend | 119 | 121 | 129 | 138 | 138 | **150** |
| Cobertura backend total | 72.76% | 73% | 72% | 72% | 72% | **72%** |
| vitest frontend | 76 | 76 | 76 | 76 | 84 | **84** |

### Decisões respondidas (Q1-Q5 do início da sub-fase)

| # | Pergunta | Resposta |
|---|---|---|
| **Q1** | Granularidade da aprovação | Por transição (batch) — todos os ScopeChanges com `baseline_to_id=this` mudam juntos. Aprovação 1-a-1 cria estado parcial absurdo. |
| **Q2** | Quando PMO rejeita, o que acontece com o baseline novo? | Adicionar `BaselineStatus.REJECTED` (preserva rastreabilidade). |
| **Q3** | Estender `diff_baselines` para `changed`? | Sim — fecha gap §10.5 literal ("adicionado/removido/**alterado**"). |
| **Q4** | Bloquear GP de `activate_baseline` em v2+? | Sim, 403 com mensagem orientando `POST /baselines/{id}/transition` (role PMO). v1 continua livre para GP. |
| **Q5** | UI PMO — rota dedicada + botões em `/diff` ou só um? | Ambos. `/pmo/scope-changes` lista portfólio-wide; `/diff` tem botões inline para revisão; badge no `/pmo/portfolio` atalha direto. |

### Decisões internas adicionais (durante construção)

- **APPROVED é skip:** approve faz transição direta `PROPOSED → IMPLEMENTED`, pulando o estado `APPROVED` do enum (commit 2). Atomicidade da decisão+implementação no MVP. Enum mantém `APPROVED` reservado para futuro caso desacoplado.
- **Description estruturada do MODIFIED** em formato single-line `"Modificado: {code} (field1: old → new, field2: old → new)"` (commit 3). Renderiza bem em telas-lista; UI rica consome `changed_fields` separadamente.
- **UX pós-decisão = navegação para `/pmo/portfolio`** em vez de refresh in-place (commit 4). PMO geralmente processa fila; toast carrega o feedback.
- **`pending_transitions_count` via 1 query agregada** `GROUP BY project_id` em vez de N+1 (commit 4).
- **Comment obrigatório em reject** validado em duas camadas: client-side (commit 4, disabled no botão) e Pydantic server-side (commit 5, via `model_validator`). ADR em `decisoes.md`.

### Conformidade — itens marcados em `docs/conformidade-v3.1.md`

- ~~E. ScopeChange: faltam baseline_from_id/to_id/change_type/approved_by~~ → endereçado em F5.2 commits 1-5
- Linha "Versionamento de escopo" §10.5 da tabela principal: ⚠️ → ✅

### Débitos menores P3 do F5.2

Todos em `docs/conformidade-v3.1.md` seção "Débitos menores de F5.2 (P3)":

| ID | Item | Onde |
|---|---|---|
| **F5.2.a** | Convenção SAEnum sem `values_callable` persiste `e.name` UPPERCASE | Aplica a todos os enums; documentado em `dev_notes.md` |
| **F5.2.b** | Testes de migration usam `importlib` (SQLite), não `alembic upgrade` real | `tests/test_migration_0014_*` e `test_migration_0015_*` |
| **F5.2.c** | Remover coluna `impact_baseline_id` legacy | `ScopeChange.impact_baseline_id`; migration de remoção em F6 |
| **F5.2.d** | `pytest-cov` subreporta cobertura de funções async | `portfolio.py` e `scope_changes.py` em 47%/50% apesar de exercício explícito; total 72% OK |

---

## F5.3 — Retrospectiva ao encerrar projeto ✅ FECHADA

Fluxo end-to-end de encerramento com retrospectiva estruturada (spec v3.1 §10.4):
GP preenche 4 campos (`delivered_vs_proposed`, `would_do_differently`, `client_feedback`,
+ lista de `materialized_risks`) → POST /projects/{id}/close → cascade de 8 validações
→ cria `ProjectRetrospective` + marca `Project.status=CLOSED` + `ended_at=today` →
UI redireciona pra `/projetos/[id]` com banner verde + render read-only da retrospectiva.

### Commits

| # | Commit | Conteúdo |
|---|---|---|
| 1 | `fe93d50` | Modelo ProjectRetrospective drop+recreate (4 campos NOT NULL + materialized_risks JSON) + migration 0016 + `.coveragerc` resolvendo F5.2.d |
| 2a | `4de0188` | `fix(backend)`: auth/register normaliza email no SELECT (bug dormente desde F2, descoberto pelo seed de teste F5.3 com case misto) |
| 2b | `93bf7bc` | `POST /projects/{id}/close` (cascade 8 validações Q4) + `GET /projects/{id}/retrospective` + schemas Pydantic + 21 testes pytest |
| 3 | `bf5b97f` | Frontend: rota `/projetos/[id]/encerramento` com form rich + Dialog + render pós-CLOSED em `/projetos/[id]`. Novo `GET /projects/{id}/risks` para pré-marcar materializados (Q1 híbrida). 11 testes vitest |
| 4 | (este commit) | 7 testes pytest do `GET /risks` (débito F5.3.c resolvido) + spec Playwright versionado + conformidade + progresso |

### Métricas (evolução durante F5.3)

| Métrica | Início F5.3 | Commit 1 | Commit 2a+2b | Commit 3 | **Commit 4 (final)** |
|---|---|---|---|---|---|
| pytest backend | 150 | 150 | 171 | 171 | **178** |
| vitest frontend | 84 | 84 | 84 | 95 | **95** |
| Cobertura backend total | (subreport 72%) → **87%** real | **87%** | **88%** | **88%** | **88%** |
| Cobertura `projects.py` | (subreport ~46%) → 67% real | 67% | 90% | 82% | **91%** |

### Decisões respondidas (Q1-Q6 do início da sub-fase)

| # | Pergunta | Resposta |
|---|---|---|
| **Q1** | materialized_risks: automático, manual ou híbrido? | (c) **Híbrido** — backend pré-popula com `Risk.status=MATERIALIZED` do projeto; GP edita livremente (adiciona/remove/comenta). |
| **Q2** | Forma de armazenar materialized_risks | (a) **JSON na coluna** — `list[{risk_id, comment}]`. FK validation em camada Pydantic via JOIN no endpoint, não SQL (JSON não suporta FK constraint nativa). |
| **Q3** | Transição CLOSED irreversível via API? | **Sim** — reabertura é caminho operacional excepcional, não exposto. Documentado no docstring do endpoint. |
| **Q4** | Matriz de bloqueios | Aprovada: ScopeChange PROPOSED, Reports DRAFT/SUBMITTED/PMO_APPROVED/NEEDS_REVISION (desvio intencional, ADR), Baseline DRAFT v2+, Project PAUSED, Project CLOSED (idempotência). Cada mensagem 409 com ação concreta. |
| **Q5** | Quem fecha? | **GP unilateral** (GP-dono). PMO não interfere. |
| **Q6** | UI: modal ou rota? | **Rota dedicada** `/projetos/[id]/encerramento` com form rich + Dialog de confirmação irreversível antes do POST. |

### Decisões internas adicionais

- **`closed_at` não duplicado como coluna** — `ProjectRetrospective.created_at` cumpre semanticamente (registro só existe quando projeto é encerrado). `Project.ended_at` (Date) é o "calendar end date" do cliente.
- **NEEDS_REVISION adicionado à lista bloqueante** — desvio intencional da spec literal (§10.4 lista 3 status). ADR registrado: NEEDS_REVISION é trabalho pendente do GP; permitir encerrar cria órfão semântico.
- **`materialized_risks` no frontend como `Map<risk_id, comment>`** — O(1) lookup, presença=marcado, valor=comment. Conversão para Array só no submit.
- **`GET /retrospective` no detail page só dispara se `status=closed`** — evita 404 ruidoso no console pra projetos ativos.

### Aprendizados marcantes da sub-fase

- **Bug dormente em auth/register descoberto** — SELECT sem `.lower()` + INSERT com `.lower()` causava 500 em vez de 409 em payload com case misto. Bug ativo desde F2; nunca acionado em produção porque clients sempre mandam lowercase. F5.3 commit 2a corrigiu em 3 linhas. Reforça a importância de tests com setup variado.
- **Cobertura real do projeto era 87%, não 72%** — `.coveragerc` com `concurrency=thread,greenlet` revelou que `pytest-cov` subreportava funções `async def`. Métricas históricas (F4, F5.1, F5.2) ficam com a anotação "medidas sem .coveragerc — números reais são maiores". A partir de F5.3, cobertura reportada é real.

### Conformidade — itens marcados em `docs/conformidade-v3.1.md`

- ~~D. Endpoint POST /projects/{id}/close + UI + ProjectRetrospective com 4 campos~~ → endereçado em F5.3 commits 1-4
- Linha "Retrospectiva" §10.4 da tabela principal: ⚠️⚠️ → ✅
- Débito F5.2.d marcado como resolvido (cobertura async)

### Débitos menores P3 do F5.3

Todos em `docs/conformidade-v3.1.md` seção "Débitos menores de F5.3 (P3)":

| ID | Item | Status |
|---|---|---|
| **F5.3.a** | Testes para paths defensivos `portfolio.py:97-116` + `scope_changes.py:51,60,98,101,103` | aberto, hardening F5.X/F6 |
| **F5.3.b** | Documentar CWD do pytest pra `.coveragerc` | parcialmente atendido em `dev_notes.md`; Makefile fica como complemento futuro |
| **F5.3.c** | `GET /projects/{id}/risks` sem teste pytest específico | **resolvido em commit 4** (7 testes novos, cobertura 82%→91%) |
| **F5.3.d** | PNGs Playwright F5.3 pendentes | aberto, mesmo problema F5.2 (ambiente local) |

---

## F5.4 a F5.9 — Pendentes

Conforme plano em `docs/fase-5-plano.md`. Ordem recomendada (conservadora: schemas estáveis antes de LGPD/deploy):

| # | Sub-fase | Estimativa | Bloqueia / é bloqueada por |
|---|---|---|---|
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

*Documento atualizado ao fim de cada sub-fase de F5 fechada. Próximo update: ao fim de F5.4.*
