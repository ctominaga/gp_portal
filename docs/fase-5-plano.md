# Fase 5 — Plano

**Status:** planejamento. **Sem código de produto.** Aguarda aprovação da divisão em sub-fases antes da primeira execução.

Volume estimado: **~390k tokens** no agregado, distribuídos em 9 sub-fases (cada uma ≤ 50k). Estouro de contexto seria certo se rodado como bloco único.

Convenção de estimativa de custo por item:

| Faixa | Marcador | Descrição |
|---|---|---|
| < 5k | **S** (small) | Item bem definido, schema simples, mudança incremental |
| 5–20k | **M** (medium) | Feature funcional com backend + frontend + testes |
| 20–50k | **L** (large) | Feature significativa, múltiplas camadas, vários testes/PNGs |
| > 50k | **XL** (xlarge) | Mudança arquitetural ou várias features juntas (deve ser quebrada) |

Os números são estimados a partir do volume tipográfico dos AJUSTES A/B/I do F4: A foi ~22k entregue, B foi ~50k entregue (mais pesado), I foi ~12k entregue.

---

## 1. Inventário consolidado

Cobre itens da spec v3.1 ainda não implementados + débitos K/L + P2/P3 da `docs/conformidade-v3.1.md`.

### Da spec v3.1

| Item | § | Estado atual | Estimativa |
|---|---|---|---|
| Modo de Report Assistido por IA | 10.2 | não implementado (busca `prepopulate` → 0) | **L ~25k** |
| Retrospectiva ao fim do projeto | 10.4 | modelo existe com schema divergente; sem endpoint `/close`; sem UI | **L ~30k** |
| Versionamento de escopo completo | 10.5 / 9.5 | `diff_baselines` cria `ScopeChange` por added/removed (idempotente); falta fluxo de aprovação PMO sobre o ScopeChange + campos `baseline_from_id/to_id/change_type/approved_by` no modelo | **L ~25k** |
| Agente de Inteligência Cruzada (Portfólio) | 6.4.3 | não implementado; task agendada via Celery Beat | **L ~30k** |
| LGPD (governança completa) | 12 | `DataProcessingRecord` modelo existe; faltam endpoints `/me/data-export`, `/me/data-deletion-request`, processo de incidentes, RAT, `docs/lgpd.md` versionado | **L ~45k** total (subdividir) |
| Exportação PDF de report | — | não implementado | **L ~30k** |
| Exportação PPTX executiva | — | não implementado | **L ~30k** |
| Deploy em produção (Railway) | — | docker-compose local OK; faltam configs Railway, DNS, env vars, monitoring | **M ~25k** |
| Hardening + feedback de GPs | (Fase 6, mas overlap) | item contínuo pós-piloto | fora do plano F5 |

### Débitos do F4 (de `conformidade-v3.1.md`)

| Débito | Origem | Estimativa |
|---|---|---|
| **F.** `Risk`: probability/impact separados + nível derivado + mitigation_plan | §4.2.3 / 9.5 | **M ~10k** |
| **G.** `ActionPlan`: `objective` + `linked_risk_id` + `linked_deliverable_id` | §4.2.4 / 9.5 | **M ~10k** |
| **H.** `Deliverable`: `acceptance_criteria` + `dependencies` + `status` (campos da spec não cobertos pelo expected.json) | §6.4.1 / 9.5 | **M ~10k** |
| **J.** `PendingItem`: `impact` + `open_date` distinto de `created_at` | §4.2.5 / 9.5 | **S ~5k** |
| **K.** F2.8 — smoke real do agente leitor + setup limpo do WSL | ADR 2026-05-11 | **L ~30k** (inclui F2.6 worker real porque compartilham pré-req) |
| **L.** Atualizar v3.1 §6.4.1 + gerar **v3.2 consolidada** | ADR 2026-05-11 adendo | **M ~15k** (escrita de spec) |

### P3 — auditorias pendentes (de `conformidade-v3.1.md`)

| Item | Estimativa |
|---|---|
| Linguagem não-técnica do Portal do Cliente: gerada por agente ou repassa GP? | **S ~5k** (investigação + decisão) |
| Histórico/linha do tempo: gráficos de tendência ou só lista? | **M ~10k** (provavelmente precisa implementar gráfico) |
| Dashboard PMO: padrões cruzados entre projetos? | **M ~10k** (talvez já coberto por §6.4.3) |
| Status do `Risk`: cobre 4 valores (Identificado/Monitoramento/Mitigado/Materializado)? | **S ~5k** |
| Fluxo de aprovação PMO sobre `ScopeChange` | já contado em E |
| Hardening de testes — consistency assertion em Playwright mocks | **M ~10k** |
| Endpoint dedicado `PATCH /reports/{rid}/delivery-progress/{dpid}` | **S ~5k** (só se UX surgir) |

**Total agregado:** schemas+features+LGPD+export+deploy+P3 = ~390k tokens.

---

## 2. Divisão em sub-fases

Critério: cada sub-fase ≤ 50k tokens estimados e produz entregável coerente (revisável independentemente).

### F5.1 — Refinamento de schemas P2 (~35k, **L**)

Backend-only, sem nova UI. Pacote único porque os 4 schemas são pequenos e correlacionados.

- F (Risk com probability/impact/level/mitigation_plan)
- G (ActionPlan com objective + 2 vinculações)
- H (Deliverable com acceptance_criteria/dependencies/status — campos da spec, **não** os do expected.json que já estão lá)
- J (PendingItem com impact + open_date)
- Migration Alembic única `0010_schema_refinement_p2`
- Atualização do schema `ProposalExtraction` se afetar (`H` sim — `acceptance_criteria`/`dependencies` viram opcionais no DTO)
- Testes pytest cobrindo nova validação
- Atualização de `worker_stub.py` se afetar fluxo de criação de baseline

**Entregável:** modelos alinhados à v3.1 §9.5; conformidade-v3.1.md marca F/G/H/J ✅.

### F5.2 — Versionamento de escopo completo (~25k, **L**)

Backend + frontend.

- Modelo `ScopeChange` ganha `baseline_from_id`, `baseline_to_id`, `change_type` (enum `added/removed/modified`), `approved_by`, `approved_at`
- Migration `0011_scope_change_refactor` (preserva dados existentes via mapeamento de `impact_baseline_id` → `baseline_to_id`)
- Endpoint `POST /scope-changes/{id}/approve` (PMO aprova) e `POST /scope-changes/{id}/reject`
- Frontend: tela de revisão de ScopeChange para o PMO (após GP fazer upload v2 e backend criar ScopeChange via `diff_baselines`)
- Testes pytest + vitest
- Regerar `f4-5-diff-propostas.png` se mudar UI

**Entregável:** versionamento de escopo funcional ponta a ponta no piloto.

### F5.3 — Retrospectiva (~30k, **L**)

Backend + frontend.

- Modelo `ProjectRetrospective` reescrito: 4 campos (`delivered_vs_proposed`, `materialized_risks`, `would_do_differently`, `client_feedback`) + `closed_at`
- Migration `0012_retrospective_schema`
- Endpoint `POST /projects/{id}/close` exige preenchimento da retrospectiva
- UI: tela `/projetos/{id}/close` com formulário guiado
- Validação: projeto não pode ser fechado sem retrospectiva preenchida
- Testes pytest + vitest + screenshot Playwright

**Entregável:** ciclo do projeto completo (criação → reports → encerramento estruturado).

### F5.4 — Modo de Report Assistido por IA (~25k, **L**)

Backend + frontend.

- Service `prepopulate_report(project_id, period)` que lê último report e gera draft inicial:
  - Riscos do anterior trazidos com prompt de confirmação
  - Entregas com prazo previsto no período em destaque
  - Sugestões geradas pelo `report_analyzer_stub` como placeholders
- Frontend: ao clicar "Novo report", oferecer "Começar do zero" vs "Pré-popular do report anterior"
- Visual hint nas linhas pré-populadas (badge "do report anterior")
- Testes pytest + vitest

**Entregável:** GP gasta < 15 min para preencher report (meta v3.1 §14.1).

### F5.5 — Agente de Inteligência Cruzada (~30k, **L**)

Backend (worker stub) + dashboard PMO.

- Modelo: `AIInsight` já tem `scope=portfolio`. Reaproveitar.
- Service `compute_portfolio_patterns()` agendado (Celery Beat, diário) que processa projetos com ≥ 3 reports
- Heurística inicial (sem agente real ainda — placeholder com base em regras claras):
  - "X% dos projetos têm RAG vermelho persistente"
  - "Risco frequente no portfólio: ..."
- Apresentação no dashboard PMO com flag "Padrões observados — sujeitos a confirmação" (v3.1 §6.4.3 — base pequena, não predizer)
- **Pré-req:** ter projetos com histórico real → recomendar implementar antes do piloto rodar uma semana, ou usar dados seed (decisão do user)
- Testes pytest

**Entregável:** dashboard PMO com seção "Padrões observados" — inicialmente baseada em regras simples; substituível pelo agente real em F6.

### F5.6 — WSL clean + F2.6 + F2.8 (~50k, **L**, limite do pacote)

Item mais pesado por compartilhar pré-req de setup.

- **Manual (Christopher):** instalar `claude` nativamente no WSL Ubuntu-22.04 conforme spec do `jump-agent-runner`. Login interativo. tmux session `project-claude` persistente.
- **F2.6** — substituir `worker_stub` por worker real:
  - Worker Python consome de Redis `jobs.agent`
  - Invoca `AgentRunner` com `ClaudeProvider` (headless) → fallback broker (tmux) → `CodexProvider`
  - Publica resultado via HTTP autenticado HMAC em `/internal/agent-results/{run_id}`
  - WorkerHeartbeat funcional
- **F2.8** — smoke real contra `bradesco_sas_databricks.expected.json`:
  - `scripts/f28_smoke_bradesco.py` (já especificado em prompt anterior)
  - Comparação automatizada por chave
  - Relatório `docs/f28-bradesco-baseline-quality.md`
- Testes E2E

**Risco:** F2.8 pode revelar que prompt v1 não bate na proposta real → cascata para v1.1 (mais um ciclo).

**Entregável:** agente leitor validado empiricamente; modo shadow do piloto pode evoluir para automático.

### F5.7 — LGPD (§12) (~45k, **L**)

Subdividir internamente em 3 passos, todos no mesmo commit final.

- (a) `docs/lgpd.md` versionado: controlador, encarregado (Christopher Tominaga é DPO designado), operadores (Anthropic, OpenAI, Cloudflare/R2, Railway, Resend), bases legais, retenção, RAT, procedimento de incidentes (~15k)
- (b) Endpoint `GET /me/data-export`: ZIP com todos os dados do titular autenticado (User, Projects que é GP/CLIENT, Reports, Approvals, AgentRunLog associados via reports). Service `data_export_service.py` (~15k)
- (c) Endpoint `POST /me/data-deletion-request`: cria `DataProcessingRecord` com `request_type=DELETION, status=PENDING`. Endpoint PMO `GET /admin/data-requests` + `POST /admin/data-requests/{id}/fulfill`. Tela frontend mínima do PMO. SLA 15 dias documentado (~15k)
- Testes pytest cobrindo cada endpoint
- **Pré-req:** estabilidade dos schemas (F5.1, F5.3 prontos)

**Entregável:** piloto Bradesco pode rodar com checklist LGPD assinado.

### F5.8 — Exportação PDF/PPTX (~50k, **L**, limite)

Backend só.

- (a) PDF de report — bibliotecas: `reportlab` ou `weasyprint` (HTML→PDF). Layout: cabeçalho, RAG, KPIs, riscos, planos de ação, pendências, destaques, próximos passos. Endpoint `GET /reports/{id}/export.pdf` (~25k)
- (b) PPTX executivo — `python-pptx`. Layout: 5-7 slides com capa, semáforo, progresso entregas (barra), riscos relevantes (linguagem cliente), próximos passos, contatos. Endpoint `GET /reports/{id}/export.pptx` (~25k)
- Testes pytest (gera arquivo + valida bytes mínimos / metadados)

**Risco:** layouts são opinativos — PMO/cliente pode pedir várias revisões. Manter v1 simples.

### F5.9 — Deploy Railway + v3.2 consolidada (~40k, **L**)

Encerramento da fase.

- (a) Deploy Railway (~25k):
  - `railway.json` ou `nixpacks.toml` para 4 serviços (frontend, backend, postgres, redis)
  - DNS aponta para `*.up.railway.app` ou domínio Jump
  - `.env.production` vs `.env.development` (vars necessárias listadas)
  - Smoke production: criar projeto → upload proposta (que vai para fila e processa via worker real F5.6) → GP preenche report → PMO aprova → cliente confirma
  - Pre-deploy checklist (LGPD assinado, sessões logadas, etc.)
- (b) v3.2 consolidada (~15k):
  - Atualizar `spec_consolidada_v3.1.md` para `v3.2` com diff explícito (regra de governança ADR 2026-05-08)
  - §6.4.1: enums do prompt v1 (9 tipos / 5 categorias / 5 complexidades)
  - Nova subseção §6.4.4 sobre `confidence_score`/`confidence_notes`
  - Mover `spec_consolidada_v3.1.md` → `spec_history/v3.1.md`

**Entregável:** produto rodando em Railway com piloto Bradesco oficial; spec atualizada.

### F5.X (opcional) — P3 hardening e auditorias (~50k, **L**)

Item residual; pode rodar **em paralelo** após F5.9 ou ficar para F6.

- Linguagem não-técnica do portal cliente — auditar/implementar (~5k)
- Gráficos de histórico/tendência no portal e dashboard (~15k)
- Padrões cruzados PMO (se F5.5 não cobriu) (~10k)
- Status do `Risk` completo (Identificado/Monitoramento/Mitigado/Materializado) (~5k)
- Consistency assertion em Playwright mocks (~10k)
- Endpoint dedicado de delivery-progress (~5k, só se aparecer demanda)

---

## 3. Dependências entre sub-fases

```
                    ┌── F5.1 (schemas P2) ──┐
                    │                        │
                    ├── F5.2 (versionamento) │
                    │                        ├──┬── F5.7 (LGPD) ──┐
                    ├── F5.3 (retrospectiva) │  │                 │
                    │                        │  │                 │
                    ├── F5.4 (modo assistido)┤  │                 │
                    │                        │  │                 │
                    │                        └──┴── F5.5 (portfolio)
                    │                                              │
F5.6 (WSL+F2.6+F2.8) ─────────────────────────────────────────────│── F5.9 (deploy+v3.2)
                                                                   │
                                                          F5.8 (PDF/PPTX) ──┘
                                                                   │
                                                            F5.X (P3 hardening)
                                                            [opcional, paralelo]
```

**Caminhos críticos:**

1. **F5.1 → F5.7** — LGPD `/me/data-export` depende de schemas estabilizados (caso contrário export muda toda vez).
2. **F5.6 (parte de Christopher) → F5.9 deploy** — produção precisa do worker real para processar uploads de propostas.
3. **F5.3 (retrospectiva) → F5.5 (portfólio)** — agente de inteligência cruzada usa dados de retrospectivas como input principal.

**Ordens viáveis:**

- **Ordem A (conservadora, schemas primeiro):** 5.1 → 5.2 → 5.3 → 5.4 → 5.6 (WSL) → 5.5 → 5.7 → 5.8 → 5.9 → 5.X
- **Ordem B (acelera deploy, schemas em paralelo):** 5.6 (WSL setup manual) + 5.1 → 5.7 (LGPD mínimo) → 5.9 (deploy beta) → resto

Recomendo **A** porque o piloto Bradesco já está em modo shadow operacional — não há pressa de deploy se isso for trocar estabilidade por agilidade.

---

## 4. Itens que requerem sua decisão antes de iniciar

| # | Pergunta | Por que precisa de você |
|---|---|---|
| 1 | **F5.5 antes ou depois do piloto rodar?** Agente de inteligência cruzada com base de dados pequena (< 10 projetos encerrados) é pouco útil, mas o dashboard fica visível mesmo assim. | Decisão de produto/UX |
| 2 | **F5.6 — Christopher instala `claude` no WSL ou eu produzo runbook + você executa?** Setup envolve subscription Team logada, ambiente isolado, tmux persistente. Não consigo fazer sozinho. | Operacional — você é o operador da máquina worker |
| 3 | **F5.7 LGPD — texto jurídico revisado por advogado externo?** Você é DPO designado. Posso produzir documento técnico (RAT, RPS, retenção), mas linguagem contratual pode exigir revisão. | Compliance |
| 4 | **F5.8 — PDF e PPTX ambos, ou só PDF inicialmente?** PPTX exige mais código (`python-pptx` tem mais arestas que `reportlab`). PDF cobre 80% dos casos. | Escopo |
| 5 | **F5.9 — Deploy beta no Railway com dados seed ou esperar piloto real autorizar?** Bradesco tem requisitos próprios (LGPD assinado, contratos de tratamento). | Compliance + cronograma |
| 6 | **F5.X — fazer dentro de F5 ou postergar para F6 (hardening contínuo)?** A spec v3.1 §10 (Plano em fases) coloca esses itens em F6. | Cronograma |
| 7 | **F5.1 — F.Risk: migrar `severity` único para `probability + impact + level`?** Atualmente `Risk.severity` é único. Migração tem implicação em todos os Risks históricos no banco. Decisão: drop+recreate ou backfill por heurística? | Migração de dados |
| 8 | **F5.6 — engine primário do worker real continua Claude ou aposta em Codex inicialmente?** Smoke F2.8 vai decidir, mas pode haver preferência de operação. | Operacional |

---

## 5. Riscos específicos de F5

### Riscos de estouro de tokens

- **F5.6 (WSL+F2.6+F2.8)** estimado em 50k mas com cauda longa: cada falha de `claude` headless força debug, cada teste E2E vira ciclo. **Mitigação:** dividir em F5.6a (setup + F2.6 worker básico) e F5.6b (F2.8 smoke) se ultrapassar 30k no meio.
- **F5.8 (PDF/PPTX)** estimado em 50k mas layouts são opinativos. **Mitigação:** v1 ultra-simples; iterar.

### Riscos de complexidade

- **F2.8 pode revelar que prompt v1 não é bom** → ciclo de revisão para v1.1 antes de mergear F5.6. Custo extra ~15k.
- **F5.2 (versionamento)** envolve migração de dados — ADRs anteriores mostram que decisões de migração mal pensadas vazam para produção.
- **F5.7 (LGPD)** depende de schemas estáveis. Se F5.1/F5.3 mudarem depois, `data-export` precisa ser atualizado (débito técnico oculto).

### Riscos de débito técnico

- **F5.5 (agente portfólio)** com regras simples pode mascarar a necessidade do agente real. Sugestão: marker visível "regras heurísticas v0 — substituir pelo agente em F6".
- **F5.9 (deploy)** sem monitoring/alerting/Sentry vira "fly by night". A spec menciona Sentry; vale incluir mesmo no v1.

### Riscos operacionais

- **F5.6 WSL setup** pode ter incompatibilidades com a versão atual do `claude` v2.1.138. Possível fallback para versão anterior.
- **F5.9 Railway** pode estourar quota de uso da subscription gratuita; pre-deploy checklist deve incluir validar plano.

### Risco do plano em si

- Este plano é **estimativa baseada em volume tipográfico dos AJUSTES do F4**. Erros de calibração de ±30% são plausíveis. Margem de segurança: tratar 50k como teto e dividir se exceder.

---

## Recomendação imediata

Sugiro iniciar por **F5.1 (schemas P2)** — é o pacote mais bem definido, sem decisão pendente sua, e libera as dependências de F5.7 (LGPD) e F5.5 (portfólio).

Antes de iniciar, peço respostas às perguntas **#1, #2, #7** da seção 4 (decisões com impacto arquitetural ou operacional). Outras podem aguardar até o ponto de execução.

---

*Plano produzido sem código de produto. Aguarda aprovação da divisão antes da primeira execução.*
