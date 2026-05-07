# Fase 3.5 — Relatório

**Status:** entregue. 7 bloqueantes/importantes corrigidos + 3 polimentos. Pronto para revisão antes de F4.

**Métricas globais:**
- Backend: 55 testes verdes (3 novos cobrindo RAG-3D, all-green dispensa justif, deviation_flag).
- Frontend: 47 testes Vitest verdes (16 novos: 11 do helper de validação RAG + 6 da tela de revisão de baseline).
- Lint + type-check + build verdes em backend e frontend.

---

## Backend (F3.5.B) — schema, validação e auditoria

**Migration `0004_rag_dimensions`:**
- `Report` ganha 6 colunas: `rag_prazo`, `rag_escopo`, `rag_qualidade` (`String(1)` nullable) + `rag_prazo_justificativa`, `rag_escopo_justificativa`, `rag_qualidade_justificativa` (`Text` nullable). `rag_status` (existente) passa a ser **agregado worst-of-3 derivado pelo backend**.
- `DeliveryProgress` ganha `revised_date` (`Date` nullable) + `deviation_flag` (`Boolean` default false).

**`POST /reports/{id}/submit` valida:**
1. As 3 dimensões obrigatórias (lista as faltantes em 400).
2. Justificativa não-vazia para cada dimensão em A ou R (com nome da dimensão na mensagem de erro).
3. Define `rag_status` agregado pelo `worst-of-3`.

**`PATCH /reports/{id}` (autosave):** quando `revised_date` é enviado e o `Deliverable.due_date` correspondente difere → `deviation_flag=true` automaticamente.

**`worker_stub.py`:** baseline.payload agora contém bloco `audit` com `source_proposal_filename`, `source_proposal_version`, `extracted_at`, `engine`, `route`, `confidence_score`. Usado pelo sub-cabeçalho da revisão.

---

## Frontend — itens corrigidos

### 1. Source excerpt EXPANDIDO por padrão (bloqueante)
Substituído `<details>` HTML por estado controlado React. Cada deliverable renderiza o trecho da proposta ao montar; botão "colapsar" inline permite ocultar caso o GP já tenha confirmado. **Arquivo:** `app/projetos/[id]/baseline/[bid]/page.tsx`.

**Screenshot:** `docs/screenshots/f35-1-baseline-source-expanded.png`

### 2. Modal de confirmação ao ativar baseline (bloqueante)
`window.confirm()` substituído por shadcn `Dialog`. Texto exato:
> "Você está aceitando **{N}** entregáveis em **{M}** fases como contrato deste projeto. Após ativação, mudanças exigirão upload de proposta v2.
> **Esta ação não pode ser desfeita.**"

Botões: `Cancelar` / `Sim, ativar baseline`. Disabled durante `activating`.

**Screenshot:** `docs/screenshots/f35-2-baseline-activate-modal.png`

### 3. RAG: 3 dimensões independentes (bloqueante)
Aba RAG do wizard reescrita. Componente `RagDimensionRow` para Prazo, Escopo, Qualidade — cada um com 3 botões `Verde`/`Amarelo`/`Vermelho`. Cor de fundo do botão ativo casa com a semântica (verde-600, amber-500, red-600). Estado armazenado em `draft.rag_prazo`/`rag_escopo`/`rag_qualidade`.

**Screenshots (válido vs. bloqueado):**
- `docs/screenshots/f35-3-4-wizard-rag-blocked.png`
- `docs/screenshots/f35-3-4-wizard-rag-ok.png`

### 4. Justificativa obrigatória em A/R (bloqueante)
Lógica isolada em `lib/rag.ts`:
```ts
validateRag({rag_prazo, rag_escopo, rag_qualidade, ...justificativas})
  → { ok, missingDimensions, missingJustifications, aggregate }
```

Quando dimensão = A ou R, `Textarea` aparece com placeholder específico: *"Por que {Prazo|Escopo|Qualidade} está em {Amarelo|Vermelho}?"*. Justificativa em branco mostra mensagem inline em vermelho. Banner âmbar consolida ao final.

**Botão "Submeter report" fica desabilitado** quando `validateRag(...).ok === false`. Aba "RAG" exibe ⚠ no título quando há pendências.

11 testes Vitest cobrindo:
- vazio → 3 dimensões faltando
- 3 verdes → ok, agregado G
- A ou R sem justificativa → bloqueia
- A com justificativa → ok, agregado A
- whitespace-only não conta como justificativa
- mistura A+R com 1 justificativa preenchida ainda bloqueia
- Verde nunca exige justificativa

### 5. `revised_date` no progresso (importante)
`DeliveryProgress` ganhou `revised_date`. Aba Progresso renderiza date input **só quando `status !== "done"` E `percent_complete < 100`**. Mostra "Prazo planejado: YYYY-MM-DD" sempre que `due_date` existe e badge âmbar `desvio` quando `revised_date != due_date`. Backend marca `deviation_flag=true` automaticamente no PATCH.

**Screenshot:** `docs/screenshots/f35-5-wizard-progress-revised.png`

### 6. Confirmação inline de critério de aceite (importante)
Quando GP marca `Concluído` no Select OU define `percent_complete = 100` num item já em `Concluído`, dispara `Dialog`:
> ✓ "Critério de aceite foi atingido?
> Marcar este entregável como Concluído com 100% indica que o critério de aceite foi cumprido. Isso entra no Health Score do projeto. Deseja continuar?"

`Cancelar` reverte, `Sim, concluído` aplica. Spec runner §5.2.7.

**Screenshot:** `docs/screenshots/f35-6-wizard-criterio-aceite.png`

### 7. Sub-cabeçalho de auditoria (importante)
Linha logo abaixo do título da revisão, fundo `bg-muted/40`:
> "Extraído de **PT 20251874 - Bradesco - Squad Migração SAS.pdf** v1 · em 07/05/2026 · via **claude**/**headless** · confiança **62%**"

Nome do arquivo é link para a proposta original. Dados vêm de `baseline.payload.audit` populado pelo worker (stub usa `engine=stub, route=stub, confidence=0.62`; o real reportará valores próprios).

Visível no screenshot do item 1.

### 8. Inconsistência 6 vs. 4 entregáveis (polimento)
Causa raiz: o screenshot do F3 mostrava 4 deliverables porque o mock de teste continha apenas 4 itens (d-001/002/003/005), enquanto o stub do backend gera 6. Corrigido o mock para conter os 6 deliverables completos, e o resumo passou a renderizar contagem dinâmica:
> *"**6** entregáveis em **3** fases."*
> *"Convergência inicial **(2)**", "Escala **(2)**", "Fechamento **(2)**"*

Header e modal de ativação também usam contagem dinâmica.

### 9. Save badge mais claro (polimento)
Substituído "não há alterações" por "Tudo salvo" + ícone `CheckCircle2`. Estados completos:
- `idle` → "✓ Tudo salvo" (outline)
- `saving` → "salvando…" (amber)
- `saved` → "✓ Salvo às HH:mm" (green)
- `error` → "falha ao salvar" (red)

Visível em screenshots f35-3-4-wizard-rag-ok.png e f35-5-wizard-progress-revised.png.

### 10. Tooltips em complexity badges (polimento)
Atributo `title` com:
- `low`: "Baixa: rotinas pequenas, dependências mínimas, baixo risco regulatório."
- `medium`: "Média: rotinas com lógica intermediária, algumas dependências entre etapas."
- `high`: "Alta: alta densidade lógica, múltiplas dependências, regras regulatórias complexas."

Aparece ao passar o mouse sobre o badge.

---

## Testes novos

### Backend (3 novos, 55 total)
- `test_submit_report_exige_rag_3d_e_justificativa_em_a_r`: 4 cenários (vazio → 400 listando dims, 1 dim → 400, 3 dims sem justif → 400, com justif → 200 com `rag_status=R` agregado).
- `test_submit_so_verde_dispensa_justificativa`: G/G/G aceita sem texto, agregado G.
- `test_revised_date_marca_deviation_flag_quando_diferente_de_due_date`: PATCH com `revised_date == due_date` → False; `revised_date != due_date` → True.

### Frontend (16 novos, 47 total)
**`tests/rag.test.ts`** (11): aggregateRag worst-of-3, worstFilled, validateRag em 8 cenários (vazio, 3G, A sem just, R sem just, A com just, whitespace-only, mix A+R, G com texto opcional).

**`tests/baseline-page.test.tsx`** (5): source_excerpt expanded por padrão (2 trechos visíveis + 2 botões "colapsar"); colapsar/expandir funcional; modal de ativação com texto exato pedido pelo PO; modal Confirmar chama POST `/baselines/{id}/activate`; sub-cabeçalho de auditoria mostra engine/rota/confidence; contador 2 entregáveis em 2 fases bate.

---

## Decisões registradas

- **`rag_status` agregado** é derivado pelo backend (não pelo frontend) no submit, garantindo consistência mesmo quando alguém bate direto na API.
- **PATCH não recalcula `rag_status` a menos que TODAS as 3 dimensões estejam preenchidas** — evita estados intermediários inconsistentes durante autosave.
- **`deviation_flag` é calculado pelo backend**, não enviado pelo cliente — frontend apenas envia `revised_date`. Evita drift quando UI não tem `due_date` em mãos.
- **Worker stub é a origem dos campos `audit`** — real worker (F2.6) reportará via callback HMAC. O contrato `baseline.payload.audit` já está estabelecido.
- **Tooltips com `title` HTML** em vez de Radix Tooltip — evita nova dependência para UI essencialmente passiva. Trocar para Radix se acessibilidade mostrar fricção real.

---

## Pronto para F4?

Os 4 bloqueantes + 3 importantes + 3 polimentos foram entregues, validados por testes unitários e capturados em 6 screenshots novos. Esperando sua aprovação dos screenshots em `docs/screenshots/f35-*.png` antes de partir para F4.

Caminho dos screenshots:
- `f35-1-baseline-source-expanded.png` — F3.5.1 + 7 + 8 (source expandido + audit + 6 deliverables)
- `f35-2-baseline-activate-modal.png` — F3.5.2 (modal de ativação)
- `f35-3-4-wizard-rag-blocked.png` — F3.5.3+4 (RAG-3D bloqueando submit)
- `f35-3-4-wizard-rag-ok.png` — F3.5.3+4 (RAG-3D válido com agregado R)
- `f35-5-wizard-progress-revised.png` — F3.5.5 (revised_date + desvio)
- `f35-6-wizard-criterio-aceite.png` — F3.5.6 (modal critério de aceite)
