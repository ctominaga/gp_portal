# Fase 4 — Relatório

**Status:** entregue. 8 sub-fases originais (Mini-ciclo A) + 3 ajustes pós-auditoria (Mini-ciclo B) + governança da spec consolidada. Pronto para revisão antes de F5.

**Métricas globais (após Mini-ciclo B):**

| Camada | Suite | Resultado |
|---|---|---|
| Backend | `pytest` | **93 passed, 1 skipped** (88s) |
| Backend | `pytest --cov` | **71.33%** geral (≥ 70%); `health_score.py` em **90%** |
| Frontend | `vitest run` | **69 passed** em 11 arquivos (25s) |
| Frontend | `tsc --noEmit` | sem erros |
| Playwright | screenshots F4 + F3.5 | **8 cenários verdes** (5 originais F4 + 2 novos F4-2/2a + 1 novo F3.5.6 com badge) |
| Migrations | Alembic | `0005` → `0009` aplicadas; coberturas testadas |
| Screenshots | `docs/screenshots/` | **12 PNGs** (6 F3.5 + 6 F4) |

---

## Mini-ciclo A — 8 sub-fases originais

Commits originais: `8897ce4` (backend), `6e20f85` (frontend), `e528f11`/`72c44df`/`e19e65e`/`af54cad` (testes Playwright).

### F4.1 — Dashboard PMO

Painel de portfólio em `/pmo/portfolio` com cards por projeto. Cada card: gauge proeminente, último RAG, contadores (riscos, críticos, pendências do cliente). Sumário consolidado (4 indicadores topo: total, health médio, distribuição G/A/R, alertas críticos). Endpoint `GET /portfolio` agrega via `health_score.compute_for_project` por projeto.

- **Evidência:** `docs/screenshots/f4-1-pmo-portfolio.png` (regerado após AJUSTE B com 5 componentes no footer; tooltip do gauge mostra breakdown completo)
- **Testes backend:** `test_portfolio_overview_pmo_lista_projetos`, `test_portfolio_overview_so_pmo_e_operator`

### F4.2 — Fluxo de aprovação PMO → Cliente

Endpoint `POST /reports/{id}/decide` com 3 decisões (originalmente `approved/rejected/requested_changes`; reescrito em AJUSTE A para `approved/approved_with_comment/requested_changes`). Estados: `submitted → pmo_approved → client_released | needs_revision`. Comentário obrigatório em revisão. `ReportApproval` registra histórico.

- **Evidência:** `docs/screenshots/f4-2-pmo-review-with-comment.png` (modal "Aprovar com comentário" preenchido) + `docs/screenshots/f4-2a-pmo-review-three-buttons.png` (header com 3 botões)
- **Testes backend:** `test_aprovacao_pmo_avanca_para_pmo_approved`, `test_aprovacao_pmo_requested_changes_exige_comentario`, `test_cliente_so_aprova_pos_pmo`, `test_aprovacao_pmo_com_comentario_exige_comment_e_libera_para_cliente`, `test_cliente_nao_ve_comment_de_aprovacao_pmo`

### F4.3 — Portal do Cliente

`/portal/projetos/[id]` com visão executiva curada. `ClientReportPublic` deliberadamente **não expõe** `comment` de aprovações (filtragem por design do schema, não condicional). Endpoint `POST /client/reports/{id}/confirm-read`.

- **Evidência:** `docs/screenshots/f4-3-portal-cliente.png`
- **Testes backend:** `test_portal_cliente_so_ve_proprio_projeto`, `test_portal_cliente_recusa_outros_projetos`, `test_cliente_nao_ve_comment_de_aprovacao_pmo`
- **Testes frontend:** `portal-cliente.test.tsx`

### F4.4 — Health Score

Cálculo + tela de configuração de pesos. **Originalmente** com 4 componentes errados (progress/risks/pendings/schedule). Reescrito em AJUSTE B para 5 componentes da v3.1 §10.3 (rag_avg/spi/risk_inverse/resolution_rate/stability). Defaults 35/25/20/10/10.

- **Evidência:** `docs/screenshots/f4-4-health-score-config.png` (regerado com 5 sliders + labels da spec + botão "Restaurar defaults")
- **Testes backend (pós-AJUSTE B):** 9 cenários cobrindo cada componente + integração + cache em `Project.health_score_cached` + classificação textual + endpoint breakdown + alias PATCH + teste documental Bradesco-like
- **Testes frontend:** `portfolio-config.test.tsx` (4 cenários: 5 dimensões, validação de soma, payload correto, defaults)

### F4.5 — Diff de propostas (versionamento)

Endpoint `GET /client/diff/{base_id}/{new_id}` calcula adicionados/removidos/alterados entre dois baselines. Função `diff_baselines` (chamada explicitamente) cria `ScopeChange` idempotente — re-chamadas não duplicam. Frontend `/projetos/{id}/diff` renderiza colunas added/removed/changed com badges.

- **Evidência:** `docs/screenshots/f4-5-diff-propostas.png`
- **Testes backend:** `test_diff_de_baselines_detecta_added_removed_changed` (cobre detecção + idempotência)
- **Testes frontend:** `diff-baselines.test.tsx`

### F4.6 — Tela de revisão de report do PMO + IAInsights

`/pmo/reports/[rid]/review` com 4 seções: RAG por dimensão com justificativa, AIInsights gerados pelo `report_analyzer_stub`, Destaques/Próximos passos, Riscos/Pendências resumidos, e o header de decisão. AIInsights renderizados com badge de severidade (info/medium/high) e `MessageSquareWarning` para alertas.

- **Evidência:** `docs/screenshots/f4-2-pmo-review-with-comment.png` (mostra AIInsights renderizados acima das ações)
- **Testes backend:** `list_report_insights` cobertura via `test_aprovacao_*`
- **Testes frontend:** `review-pmo.test.tsx` (6 cenários após AJUSTE A)

### F4.7 — Notificações in-app + SSE + email

`InAppNotification` persistido por usuário. Endpoints `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`. Sino com contador no `AppShell`. SSE em `GET /events/stream`. `notify_approval_decision` dispara notificação contextualizada por estado do report (após AJUSTE A, diferencia `report_pmo_approved` vs `report_pmo_approved_with_comment` com nota interna no body).

- **Testes backend:** `test_notifications_unread_count_e_mark_read`

### F4.8 — Screenshots Playwright

5 cenários originais (F4-1 a F4-5) + helper `assertReactUiRendered` anti-regressão (decisão em `decisoes.md` 2026-05-08). Specs usam URL absoluta do API server em vez de glob amplo (lição aprendida do bug de Playwright F4-1 onde `**/portfolio` interceptava tanto API quanto navegação Next).

- **Cenários verdes:** F4-1, F4-2 (regerado), F4-2a (novo), F4-3, F4-4 (regerado), F4-5 + anti-regressão (`assertReactUiRendered falha em página JSON cru`)

---

## Mini-ciclo B — 3 ajustes pós-auditoria + governança

Aberto após auditoria de conformidade contra spec consolidada v3.1.

### Governança da spec (commits `48b4370`, `3981f4d`, `76404e6`, `1fe45a6`)

A v3.0 original era um delta da v2.1 (que nunca existiu como arquivo standalone). Resultado: implementação prosseguiu sem fonte autossuficiente; auditoria revelou que 3 das prescrições principais da v2.0/v2.1 estavam ausentes da v3.0:
- §10.1 — Aprovação em 3 estágios
- §10.3 — Health Score com 5 componentes
- §4.2.2 — Persistência da confirmação de critério de aceite

Consolidação produzida em `docs/spec_consolidada_v3.1.md` (autossuficiente, substitui v2.0/v2.1/v3.0). Versões antigas em `docs/spec_history/` (`v3.0.md` movido da raiz, `v1.0.pdf` movido do Downloads). Política para futuras versões registrada em `decisoes.md` 2026-05-08 (ADR "Governança — Spec consolidada v3.1 vira fonte única").

Tabela de conformidade em `docs/conformidade-v3.1.md` mapeia implementação atual contra a v3.1 em 3 dimensões (módulos funcionais §4, modelo de dados §9.5, melhorias §10), com priorização P1/P2/P3.

### AJUSTE A — Aprovação em 3 estágios (commit `1b9123c`)

Substitui `ApprovalDecision.REJECTED` (não existia no domínio do produto) por `APPROVED_WITH_COMMENT`. Validação: comentário obrigatório quando `requested_changes` ou `approved_with_comment`; opcional em `approved` direto.

**Backend:**
- Enum em `domain.py` reescrito.
- `_next_status` trata APPROVED_WITH_COMMENT como APPROVED (mesmo destino de status).
- Migration `0006_approval_with_comment`: UPDATE rows legadas (não havia native enum no Postgres — coluna era `String(30)`).
- `notify_approval_decision` distingue notificação `report_pmo_approved` vs `report_pmo_approved_with_comment` com corpo incluindo a nota interna.

**Frontend:**
- 3 botões no header de `pmo/reports/[rid]/review`: `[Pedir revisão]` (outline), `[Aprovar com comentário]` (outline-emphasis), `[Aprovar]` (primário).
- 3 dialogs com copy distinta. Modal "Aprovar com comentário" comunica **explicitamente**: *"O comentário é nota interna ao GP, não aparece no portal do cliente"*.
- Histórico mostra ícone + label distintos por decisão; comment de `approved_with_comment` marcado `[nota interna]`.

**Isolamento estrutural:** `ClientReportPublic` (`schemas/client.py`) não expõe campo `comment` — filtragem por design do schema, não condicional. Teste `test_cliente_nao_ve_comment_de_aprovacao_pmo` verifica via substring negativa.

**Evidências:** `f4-2-pmo-review-with-comment.png`, `f4-2a-pmo-review-three-buttons.png`.

### AJUSTE B — Health Score 5 componentes (commits `f7bed61`, `5a17e1e`, `9a3c19b`)

Refeito do zero. 5 componentes da v3.1 §10.3, cada um função pura por componente + `compute_for_project` orquestra:

```
Health Score = (rag_avg × 0.35) + (spi × 0.25) + (risk_inverse × 0.20)
             + (resolution_rate × 0.10) + (stability × 0.10)
```

**Backend:**
- `PortfolioConfig` migra de 4 colunas para `health_score_weights` JSONB. Migrations `0007` (add) + `0008` (drop colunas antigas) separadas para seguir regra de deploy seguro.
- Defaults 35/25/20/10/10 ancorados na spec. Pesos antigos **não migram numericamente** (componentes mudaram semanticamente).
- `Project.health_score_cached` (Float nullable) para listagens rápidas. `cache_to_report` atualiza após cada submit.
- Endpoint `GET /projects/{id}/health-score-breakdown` retorna 5 componentes para tooltip do gauge.
- Validação Pydantic `HealthScoreWeights` exige soma=1.00±0.01 em PUT/PATCH `/portfolio/config`.

**Heurística da Estabilidade** (registrada como decisão refinável em piloto):

| Condição (últimos 5 reports) | Valor |
|---|---|
| ≥5 todos no mesmo rag | 100/50/0 (G/A/R) |
| ≥3 todos no mesmo rag | 60 |
| Oscilação ou < 3 reports | 30 |
| Sem reports | 50 |

**Frontend:**
- Tela de config com 5 sliders + descrições da v3.1 §10.3 + botão "Restaurar defaults (35/25/20/10/10)".
- Cards do dashboard mostram 5 componentes no footer (`RAG · SPI · Risco⁻¹ · Resol. · Estab.`); gauge com `title` HTML mostra breakdown completo.

**Validação matemática (teste documental — commit `9a3c19b`):** cenário Bradesco-like com 5 deliverables + 5 reports submetidos + 1 risco crítico + 4 pendências resolvidas + 1 aberta produz `rag_avg=83.3, spi=75.9, risk_inverse=0, resolution_rate=80, stability=30 → score=59.1 (band amber)`. Asserts garantem matemática individual.

**Fix correlato (commit `5a17e1e`):** corrige inconsistência matemática no mock do Playwright F4-1 — Bradesco tinha `score=81.8` quando soma ponderada dos componentes dava 79.55. Bug do mock apenas; cálculo real correto.

**Evidências:** `f4-1-pmo-portfolio.png` (5 componentes no footer), `f4-4-health-score-config.png` (5 sliders).

### AJUSTE I — Persistir `acceptance_confirmed` (commit `558d56c`)

Bug silencioso: modal F3.5.6 "Critério de aceite foi atingido?" perguntava mas não persistia. Adicionado campo `DeliveryProgress.acceptance_confirmed: bool | None` (migration `0009`). Validação no PATCH: `status=done + percent_complete=100` sem `acceptance_confirmed=True` → 400. Handler do modal `"Sim, concluído"` agora envia a flag; badge verde `✓ aceite confirmado` no card quando true.

**Decisão arquitetural:** mantém PATCH único `/reports/{rid}` (não criou endpoint dedicado `/delivery-progress/{dpid}`) — equivalente com menos superfície de API. Endpoint dedicado fica como débito trivial caso UX de "confirmar aceite isolado" surja no piloto.

**Evidências:** `f35-6-wizard-criterio-aceite.png` (regerado, mostra estado pós-confirmação com badge).

### Preparações independentes para F5 (commits `29ec418`, `4ff46fe`, `4d9e260`)

- **Schema `ProposalExtraction`** Pydantic (`backend/app/schemas/proposal_extraction.py`) com 3 enums fechados alinhados ao prompt v1, regex de id `^d-\d{3}$`, limite de `source_excerpt` 500 chars, cross-field validators (phase refs, deliverable_count, ids únicos), validador de `confidence_score < 80 ⇒ notes não-vazias`.
- **Prompt versionado** `docs/prompts/proposal_reader_v1.md` — ancorado na proposta gold-standard Bradesco. 9 regras duras (R1-R9), incluindo R1 "nunca inventa entregáveis", R2 "não extrai datas por item", R4 "source_excerpt literal", R8 "apenas cenário recomendado".
- **Alinhamento schema ↔ prompt** (commit `4d9e260`): schema inicialmente herdou enums da v3.1 §6.4.1 (Documento/Software/...) que o prompt v1 não usa. Realinhado: 9 tipos do prompt, 5 categorias, 5 níveis de complexidade. v3.1 §6.4.1 fica como divergência **intencional** que vai virar v3.2 (débito L).

### F2.8 adiado para F5 (commit `76404e6`)

Smoke real do agente leitor contra `bradesco_sas_databricks.expected.json` foi tentado e bloqueou em três pré-requisitos: (a) sessão WSL `project-claude` estava parada (Ubuntu-22.04 stopped); (b) `claude` CLI v2.1.138 instalado no Windows e acessado via mount WSL apresentou comportamento errático em modo headless após login interativo bem-sucedido; (c) setup não atende à spec do `jump-agent-runner` que pede `claude` instalado nativamente no WSL Linux.

Decisão: adiar F2.8 para F5 (sub-task explícita, compartilha pré-requisito com F2.6). Piloto Bradesco entra em **modo shadow** (v3.1 §1.5) — extração apresentada como sugestão, baseline só ativado após revisão manual completa.

---

## Débitos declarados para F5

Lista priorizada. P1 já foram endereçados nos ajustes A/B/I de Mini-ciclo B; P2 e P3 ficam para F5.

### P2 — débito funcional (não bloqueia fechar F4)

Referência: `docs/conformidade-v3.1.md` (seções "Prioridade 2" e "Débitos F5").

- **C.** Modo de Report Assistido por IA (§10.2) — pré-popula draft com base no report anterior
- **D.** `POST /projects/{id}/close` + UI + `ProjectRetrospective` com 4 campos estruturados (§10.4)
- **E.** `ScopeChange`: faltam `baseline_from_id`, `baseline_to_id`, `change_type`, `approved_by` (§10.5/9.5)
- **F.** `Risk`: falta probability/impact separados + `mitigation_plan` (§4.2.3/9.5)
- **G.** `ActionPlan`: falta `objective`, `linked_risk_id`, `linked_deliverable_id` (§4.2.4/9.5)
- **H.** `Deliverable`: falta `acceptance_criteria`, `dependencies`, `status` (§9.5)
- **J.** `PendingItem`: falta `impact` e `open_date` distinto (§4.2.5/9.5)
- **K.** F2.8 — smoke real do agente leitor com setup limpo do WSL (instala claude nativo, roda smoke, gera `f28-bradesco-baseline-quality.md`). Compartilha pré-requisito com F2.6 (worker real).
- **L.** Atualizar v3.1 §6.4.1 com enums do prompt v1, documentar `confidence_score`/`confidence_notes`, gerar **v3.2 consolidada** seguindo regra de "diff explícito do que foi alterado".

### P3 — auditoria pendente / hardening

- Linguagem não-técnica do Portal do Cliente: gerada por agente ou só repassa texto do GP? (§4.3)
- Histórico/linha do tempo: existem gráficos de tendência ou só lista de reports? (§4.5)
- Gráficos do dashboard PMO: padrões cruzados entre projetos? (§4.4)
- Status do `Risk` cobre os 4 valores da spec (Identificado/Monitoramento/Mitigado/Materializado)? Vi só `OPEN` no modelo
- Fluxo de aprovação do PMO sobre `ScopeChange` (não só criação automática) (§10.5)
- **Hardening de testes — mock pode mentir matematicamente:** mock do Playwright F4-1 tinha `score` inconsistente com soma ponderada dos `components`, nenhum teste pegou. Padrão vai aparecer em outros mocks. Sessão dedicada de "consistency assertion" pre-flight nos specs.
- Endpoint dedicado `PATCH /reports/{rid}/delivery-progress/{dpid}` (alternativa ao PATCH único atual) — débito trivial; só fazer se UX de "confirmar aceite isolado" surgir.

---

## Decisões arquiteturais (resumo de `decisoes.md`)

Decisões tomadas durante F4 que merecem registro com links para detalhe.

### 2026-05-08 — Governança / Spec consolidada v3.1 vira fonte única
Substitui v2.0/v2.1/v3.0. Política: toda nova versão é autossuficiente (não delta), começa com diff explícito da anterior, anterior vai para `spec_history/`.

### 2026-05-08 — Mocks Playwright usam URL absoluta do API server
Glob amplo `**/portfolio` casava tanto API quanto navegação Next, devolvendo JSON em vez de HTML. Helper `assertReactUiRendered` adicionado como anti-regressão.

### 2026-05-11 — F4 / AJUSTE A — Aprovação com comentário (3 estágios v3.1 §10.1)
Substitui `REJECTED` por `APPROVED_WITH_COMMENT`. Isolamento do `comment` via design do schema `ClientReportPublic`, não condicional.

### 2026-05-11 — F4 / AJUSTE B — Health Score reescrito para 5 componentes (v3.1 §10.3)
Migra `PortfolioConfig` de 4 colunas para JSONB. Pesos antigos não migram numericamente. Heurística de Estabilidade documentada e refinável em piloto.

### 2026-05-11 — F2.8 adiado para F5 com setup limpo do WSL
`claude` CLI v2.1.138 errático em headless via mount WSL. F2.8 e F2.6 compartilham pré-requisito de setup limpo (claude nativo no WSL Linux). Mitigação: modo shadow no piloto. **Adendo:** enums do schema `ProposalExtraction` alinhados ao prompt v1 (fonte); v3.1 §6.4.1 vira débito L para a v3.2.

---

*Esta fase entrega o produto pronto para o cenário operacional do piloto Bradesco em modo shadow. F5 abre com (a) endereçar os P2 do backlog, (b) executar F2.8/F2.6 em setup WSL limpo, (c) consolidar v3.2 com o vocabulário alinhado, (d) auditar os pendentes P3.*
