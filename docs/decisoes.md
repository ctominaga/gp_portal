# Registro de decisões técnicas — ADRs

Decisões tomadas durante a construção que merecem registro. Convenção: cabeçalho com data e título; corpo curto com contexto, decisão e consequência.

## 2026-05-06 — F0 / Estrutura inicial

**Contexto:** prompt-mestre define monorepo com 4 áreas (backend, frontend, jump_agent_runner, worker). Não é repo git ainda; raiz `Jump-GP-portal/` contém os 4 .md de spec.

**Decisão:** monorepo vive em subpasta `jump-report/`, dentro de `Jump-GP-portal/`. As specs `.md` ficam fora do monorepo. Remote git aponta para `https://github.com/ctominaga-jump/gp_portal.git`.

**Consequência:** specs não viajam com o repo; `docs/` interno do monorepo é a fonte de verdade durante a construção.

## 2026-05-06 — F0 / Propostas reais como fixtures gold-standard

**Contexto:** prompt-mestre pedia 3 propostas sintéticas geradas em PT-BR. O usuário forneceu 3 propostas reais em `propostas/` (Bradesco SAS→Databricks, Torra Governança, PTC 20262113 Diretriz Estratégica).

**Decisão:** usar as propostas reais como fixture gold-standard. PDFs ficam fora do git (são grandes, alguns >50MB). Texto extraído via `pypdf` é commitado em `backend/tests/fixtures/proposals/<nome>.txt`. `<nome>.expected.json` com backlog anotado também é commitado.

**Consequência:** validação do agente leitor é feita contra dados reais, com aderência muito maior. Quem clonar o repo precisa ter os PDFs originais para rodar testes que carregam PDF; testes que usam só texto extraído rodam em qualquer ambiente.

## 2026-05-06 — F0 / Cobertura mínima ativa só a partir da F1

**Contexto:** princípio de engenharia 1 exige ≥70% de cobertura no backend e no agent-runner a partir da F1. Em F0 ainda não há código de domínio para testar.

**Decisão:** `pytest` em F0 não enforce cobertura; a partir do primeiro commit da F1 (S0 do agent-runner) passamos a impor `--cov-fail-under=70` no CI, configurado por workflow.

**Consequência:** F0 fica enxuta (só smoke test placeholder). Risco controlado: se tests não forem escritos em S0, a barra não começa a ser respeitada.

## 2026-05-06 — F0 / Resend usa email pessoal corporativo até domínio jump.tec.br ser verificado

**Contexto:** Resend exige domínio verificado para enviar a partir dele. O domínio definitivo `jump.tec.br` ainda não foi configurado.

**Decisão:** `RESEND_FROM_EMAIL` aponta para `christopher.tominaga@jumplabel.com.br` (email pessoal corporativo do Christopher, já em domínio jumplabel.com.br) durante o piloto. Trocar para `notificacoes@jump.tec.br` (ou similar) quando o DNS estiver configurado, na Fase 5.

**Consequência:** notificações iniciais sairão do email pessoal do dono do produto — aceitável para piloto, não ideal para produção em escala.

## 2026-05-07 — F0 / Portas do compose parametrizadas para evitar conflito local

**Contexto:** na máquina do dev as portas 5432 (Postgres) e 3000 (Node) estavam ocupadas por outros processos host — Postgres do OpenMetadata e algum dev server Node. Subir o compose colidiria.

**Decisão:** parametrizar os mapeamentos de porta no `docker-compose.yml` com defaults non-default (`POSTGRES_HOST_PORT=55432`, `REDIS_HOST_PORT=56379`, `BACKEND_HOST_PORT=8000`, `FRONTEND_HOST_PORT=13000`). Quem quiser usar 5432/3000 sobrescreve via `.env`. Ports internas dos containers seguem padrão (5432/6379/8000/3000); só o host muda.

**Consequência:** `/health-check` aponta para `http://localhost:8000` e o frontend é servido em `:13000`. README atualizado nesse sentido na próxima iteração.

## 2026-05-07 — F0 / Pin de Next.js corrigido para 14.2.35 (CVE)

**Contexto:** `next@14.2.18` tem CVE divulgada em 2025-12-11. `npm install` warna explicitamente.

**Decisão:** pin para `next@14.2.35` e `eslint-config-next@14.2.35` (último 14.2.x patch disponível no momento). Mantém major Next 14 conforme stack obrigatória do prompt.

**Consequência:** sem mudança funcional; package-lock regerado limpo após `rm -rf node_modules` (workaround para bug `Invalid Version` do Arborist com lock antigo).

## 2026-05-07 — F0 / Validação Docker pendente / contornada com pytest+vitest locais

**Contexto:** durante a validação F0, Docker Desktop entrou em estado degradado (comandos `docker ps`, `docker images`, `docker compose build` timeoutavam ou hangavam após o `docker system prune -a -f --volumes`). Reinício do Docker Desktop só estabilizou parcialmente.

**Decisão:** validação local de `docker compose up` é remetida ao próximo ciclo (quando Docker estiver estável). No lugar, validamos:
- `pytest` no backend rodando com Python 3.12 e venv local — 1 teste passou em 0.56s.
- `vitest` no frontend com Node 24 e Next.js 14.2.35 — 1 teste passou em 9ms.
- `docker compose config --services` retorna todos os 4 serviços (YAML válido).
- CI do GitHub Actions exercita o `docker compose` em Linux limpo — usado como fonte de verdade até Docker local estabilizar.

**Consequência:** `/health` e `/health-check` end-to-end ainda não foram observados rodando localmente. Esse smoke fica como item explícito de "validar antes de F1.S0", quando o Docker da máquina worker for o mesmo onde o agent-runner vai rodar.

## 2026-05-11 — F2.8 adiado para F5 com setup limpo do WSL

**Contexto:** tentativa de executar o smoke real do agente leitor (F2.8) contra a proposta gold-standard do Bradesco revelou que o `claude` CLI v2.1.138, instalado no Windows e executado via mount WSL, tem comportamento errático: login interativo via TUI (`claude /login`) reporta "Login successful", mas invocação headless (`claude -p`) imediatamente depois retorna "Not logged in · Please run /login". Bug ou incompatibilidade entre subscription Team e modo headless da versão atual.

Setup atual também não atende à spec do `jump-agent-runner`, que assume `claude` instalado **nativamente no WSL Linux** com configuração isolada (não binário Windows acessado por mount). Resolver isso é pré-requisito de F2.6 (worker real) e de F2.8 (smoke), então ambos serão endereçados juntos em F5.

**Decisão:**
1. Adiar F2.8 para F5 como sub-task explícita.
2. Em F5, criar sub-tarefa para: (a) instalar `claude` nativamente no WSL (Ubuntu-22.04), (b) executar F2.8 nesse setup limpo, (c) executar F2.6 (worker real) no mesmo setup.
3. Mantém preparação útil que pode ser feita agora: prompt versionado `proposal_reader_v1.md` (quando recebido) e schema Pydantic `ProposalExtraction`. Não dependem do WSL.

**Consequência:** piloto Bradesco entra com agente leitor **não-validado empiricamente** contra proposta real. Mitigação é o **modo shadow** já previsto na spec v3.1 §1.5: extração apresentada como sugestão, baseline só ativado após revisão manual completa do GP. Não é decisão de "modo manual permanente" — é validação adiada.

**Risco residual aceito:** a aposta arquitetural do agente leitor já foi validada em F1 com smokes triviais. A qualidade da extração real contra proposta complexa do Bradesco ficará conhecida na primeira semana de piloto. Se a precisão for baixa, decisão de subir para modo automático fica adiada — não há perda operacional irreversível.

**Adendo 2026-05-11 (continuação)** — enums do schema `ProposalExtraction` alinhados ao prompt `proposal_reader_v1.md` que é fonte:

- `DeliverableType`: 9 valores (`code_migration / documentation / knowledge_transfer / stabilization / deliverable_software / assessment / model / infrastructure / other`). A v3.1 §6.4.1 listava `Documento/Software/Serviço/Treinamento` (delta esquecido no rascunho da spec). O prompt vence porque é o que o agente realmente produz; a v3.1 §6.4.1 será atualizada na próxima edição da spec (**v3.2** — débito L).
- `DeliverableCategory`: 5 valores incluindo `negocio` e `governanca` que faltavam.
- `DeliverableComplexity`: 5 níveis incluindo `media` (não só baixa/baixa-media/media-alta/alta).
- `ProposalExtraction` ganha campos top-level `confidence_score: int [0..100]` e `confidence_notes: list[str]`, com validator que exige `confidence_notes` não-vazia quando `confidence_score < 80` (prompt §5).
- Sem migration de banco: `Baseline.payload` é JSONB, validação acontece em runtime na entrada (DTO) e na saída (publicação ao backend).

## 2026-05-11 — F4 / AJUSTE B / Health Score reescrito para 5 componentes (spec v3.1 §10.3)

**Contexto:** auditoria contra a v3.1 mostrou que a implementação original tinha 4 componentes (progress / risks / pendings / schedule) com fórmulas que não correspondiam às prescrições da spec — em particular `progress` (% concluído bruto) era usado em vez de "Status RAG médio", `schedule` (% sem deviation_flag) em vez de SPI real÷planejado, e Estabilidade do status RAG não era computada. Pesos defaults eram 40/20/20/20, divergentes do 35/25/20/10/10 ancorado na spec.

**Decisão:**
1. `PortfolioConfig` migra de 4 colunas (`weight_progress/risks/pendings/schedule`) para coluna única JSONB `health_score_weights` com 5 chaves (`rag_avg`, `spi`, `risk_inverse`, `resolution_rate`, `stability`). Migrations 0007 (add JSONB) + 0008 (drop colunas antigas) separadas para seguir regra de deploy seguro (add → migrate consumers → remove). Em piloto sem dados de produção, ambas aplicam de uma vez; em produção real seriam dois deploys.
2. **Pesos antigos NÃO migram numericamente** para o novo JSONB. Os componentes mudaram semanticamente (3 dos 5), então um peso 0.40 em `weight_progress` não tem correspondência em `rag_avg`. Defaults da spec (35/25/20/10/10) ancoram a configuração; PMO reajusta na UI se necessário.
3. Adiciona `Project.health_score_cached` (Float nullable) para listagens rápidas; `cache_to_report` atualiza tanto `Report.health_score` quanto `Project.health_score_cached` no submit.
4. Validação Pydantic exige soma = 1.00 ± 0.01 no PUT/PATCH `/portfolio/config`. Defensivo: o serviço também normaliza no momento do cálculo.
5. Novo endpoint `GET /projects/{id}/health-score-breakdown` retorna os 5 componentes individuais para tooltip do gauge.

**Heurística da componente Estabilidade:** a spec v3.1 §10.3 prescreve "5+ reports no mesmo Verde = 100; 5+ no mesmo Vermelho = 0; oscilação = 50" e Christopher confirmou abertura para refinar matematicamente. Implementação:

| Condição (últimos 5 reports submetidos) | Valor |
|---|---|
| ≥5 reports e TODOS no mesmo rag (worst-of-3) | 100 se Verde, 50 se Amarelo, 0 se Vermelho |
| ≥3 reports e TODOS no mesmo rag | 60 (estabilidade mediana, ainda não maturidade plena) |
| Qualquer oscilação ou < 3 reports | 30 (instável ou histórico curto) |
| Sem reports | 50 (neutro — não há base) |

Refinável após piloto com PMO real. O valor "50 para amarelo estável" foi mantido conforme spec mesmo parecendo contraintuitivo (estabilidade alta deveria ser positiva): a interpretação é que "estar consistentemente em alerta é diferente de estar consistentemente saudável". Score puxa para baixo só em consistente vermelho, sobe em consistente verde — alinhado com o produto.

**Consequência:**
- Cards do dashboard PMO mostram os 5 componentes (`RAG · SPI · Risco⁻¹ · Resol. · Estab.`) em vez dos 4 antigos. Tooltip no gauge tem breakdown completo.
- Tela `/pmo/portfolio/config` tem 5 sliders + botão "Restaurar defaults (35/25/20/10/10)".
- Scores recalculados podem mudar — esperado e correto. Os valores antigos eram errados por definição.

## 2026-05-08 — Governança / Spec consolidada v3.1 vira fonte única, deprecando v2.0, v2.1 e v3.0

**Contexto:** auditoria do F4 revelou que a v3.0 (escrita como delta da v2.1) omitiu prescrições funcionais que a equipe assumia válidas (3 estágios de aprovação do PMO, fórmula Health Score com 5 componentes, retrospectiva, versionamento de escopo, modo assistido). A v2.1 nunca existiu como arquivo standalone — era delta da v2.0 mantido só na conversa. Implementação prosseguiu sem fonte única, e a tela de revisão do PMO acabou com 2 ações (não 3) e Health Score com 4 dimensões (não 5) sem registro deliberado dessa redução.

**Decisão:** `docs/spec_consolidada_v3.1.md` é a fonte funcional canônica única, autossuficiente. Substitui v2.0, v2.1 e v3.0. As versões anteriores ficam em `docs/spec_history/` (`v3.0.md` movida da raiz `Jump-GP-portal/`, `v1.0.pdf` movida de `~/Downloads`) como referência histórica — **não devem ser usadas como fonte de prescrição**.

**Política para futuras versões da spec:**
- Toda nova versão é autossuficiente, **não delta**
- Toda nova versão começa com diff explícito (alterado / removido / adicionado) em relação à anterior, no cabeçalho do documento
- Versão anterior é movida para `docs/spec_history/v<N>.<m>.md` no mesmo commit que sobe a nova
- README aponta sempre para a versão canônica atual

**Consequência:** desvios da implementação atual contra a v3.1 viram backlog de ajustes rastreável (tabela de conformidade no próximo commit). Memória do produto registra v3.1 como referência, não mais "4 .md na raiz". Specs `02_jump_agent_runner_spec.md`, `03_prompt_claude_code.md`, `04_decisoes_operacionais.md` permanecem na raiz `Jump-GP-portal/` por enquanto — só a spec funcional foi consolidada.

## 2026-05-08 — F4 / Mocks Playwright usam URL absoluta do API server, não glob amplo

**Contexto:** durante geração de screenshots do F4, o spec usava `page.route("**/portfolio", ...)`. O glob `**/portfolio` casa qualquer URL terminada em `/portfolio` — então tanto a chamada da API (`http://localhost:8000/portfolio`) quanto a navegação Next (`http://localhost:3100/pmo/portfolio`) eram interceptadas e devolviam JSON. O browser exibia o JSON cru com pretty-print, e o `waitForSelector("text=SAS→Databricks")` "passava" porque a string aparece tanto no `project_name` do JSON quanto na UI esperada. O PNG comitado era do JSON, não da UI.

**Decisão:** todo `page.route()` em specs Playwright deve usar URL absoluta com escopo do API server (constante `API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`), não glob amplo `**/...`. Aplicado preventivamente também em `screenshots.spec.ts` (F3.5), que estava OK por sorte de naming (frontend usa `/projetos`, backend `/projects`) mas era frágil.

**Consequência:** mocks deixam de competir com o roteamento do Next. Adicionado helper `assertReactUiRendered(page)` no spec F4 (verifica >=1 `<h1>`) chamado antes de cada `page.screenshot()`, com teste negativo que injeta o bug e confirma que o helper rejeita. Próximos specs Playwright que usem `page.route()` devem seguir essa convenção.

## 2026-05-12 — F5.2 / Comment obrigatório em reject de transição: validação Pydantic

**Contexto:** `POST /baselines/{id}/transition` com `decision="reject"` aceitava `comment=null` ou `comment=""`. Sem justificativa, a rejeição é uma caixa-preta para o GP — ele recebe a notificação "PMO rejeitou", mas não sabe o quê ajustar. UI já fazia validação client-side (botão Confirmar desabilitado sem texto), mas chamada direta à API contornava.

**Decisão:** validação em `TransitionDecisionPayload` via `@model_validator(mode="after")`. `decision == "reject"` exige `comment` não-vazio (após strip). `decision == "approve"` mantém `comment` opcional — aprovação tácita é caso de uso legítimo (PMO acompanhou em reunião e libera sem nota interna). FastAPI converte `ValidationError` em 422 automaticamente.

**Consequência:** UI continua validando client-side (UX imediato), backend reforça (defesa em profundidade). Testes: `test_reject_empty_comment_returns_422`, `test_reject_whitespace_only_comment_returns_422`, `test_reject_with_valid_comment_returns_200`, `test_approve_without_comment_returns_200`. Não há migração — escrita histórica seguia o caminho da UI, então não há dados malformados a corrigir.

## 2026-05-12 — F5.2 / Convenção SAEnum: persistência usa e.name, não e.value

**Contexto:** durante a migration 0014 (F5.2 commit 1), backfill inseriu `change_type='added'` (lowercase, igual ao `e.value` definido em Python). ORM falhava ao ler com `LookupError`. Inspeção empírica de `SAEnum._object_lookup` revelou que sem `values_callable`, SAEnum persiste e lê o **name** do membro (`'ADDED'`, UPPERCASE). Vale para todos os enums do projeto que herdam de `(str, enum.Enum)`.

**Decisão:** documentar convenção em `docs/dev_notes.md` (criado nesta sessão). Todo SQL literal em migration que mexe em coluna de enum deve usar o `e.name` (UPPERCASE). Reescrita por meio do ORM segue funcionando direto com membros do enum Python. Não introduzir `values_callable` retroativamente — quebraria todos os dados existentes.

**Consequência:** débito P3 `F5.2.a` registrado em `conformidade-v3.1.md`. Migrations futuras que mexam em enum devem consultar `dev_notes.md` antes. Server_defaults em SQL atuais (`server_default="active"`, etc.) são inconsistentes com essa convenção mas não causam bug porque o ORM sempre passa o membro Python explicitamente — server_default só dispara em insert sem valor, que não ocorre em código atual.

## 2026-05-12 — F5.3 / Encerramento bloqueia reports em NEEDS_REVISION (desvio da spec literal)

**Contexto:** spec v3.1 §10.4 implica que reports "em fluxo" bloqueiam o encerramento de projeto. A lista canônica de "em fluxo" do projeto era DRAFT/SUBMITTED/PMO_APPROVED — workflow de aprovação 3 estágios da §10.1. NEEDS_REVISION foi adicionado em F4 como retorno explícito do PMO ao GP ("ajuste e re-submeta"), mas a spec §10.4 não atualizou a lista para incluí-lo.

**Decisão:** incluir `NEEDS_REVISION` em `_REPORT_BLOCKING_STATUSES` (`app/api/v1/projects.py`). Permitir encerrar projeto com report em NEEDS_REVISION cria órfão semântico — PMO pediu correção, GP simplesmente fecha o projeto sem responder; o registro fica "preso" naquele estado intermediário sem nunca ter sido revisitado. Comentário inline na constante referencia este ADR.

**Consequência:** terceiro caso de governança de desvio em F5 (junto com v3.1 §6.4.1 desatualizada vs prompt v1, e enums realinhados de F5.1 Deliverable). Padrão saudável: spec é fonte, desvios são documentados. v3.2 (consolidada futura) deve atualizar §10.4 para listar os 4 status. Sem migração de dados — é uma regra de validação, não schema.

## 2026-05-12 — F5.3 / `auth/register` normaliza email no SELECT (case-sensitive bug)

**Contexto:** descoberto em F5.3 commit 2 durante setup de teste. Handler `POST /auth/register` (commitado na F2) tinha inconsistência: SELECT de unicidade usava `payload.email` cru, mas INSERT usava `payload.email.lower()`. Em produção, clients reais (frontend, scripts) sempre mandam lowercase, então o bug nunca foi acionado. No teste, `_seed_project_for_close` criou User com `"gp-A422@x.com"` (case misto) e `_login` reenviou para `/auth/register` — SELECT não bateu (banco tem `"gp-a422@x.com"`), INSERT tentou gravar lowercase, UNIQUE constraint disparou `500 IntegrityError` em vez do `409` esperado.

**Decisão:** normalizar `payload.email.lower()` antes do exists-check no register. 3 linhas alteradas. Sem mudança de contrato externo — clients que já mandam lowercase continuam idênticos. Fix isolado em commit dedicado (`fix(backend): auth/register normaliza email no SELECT`).

**Consequência:** 500 vira 409 para edge case de case-misto. Sintoma é menos feio em logs / Sentry. Bug dormente desde F2, eliminado sem regressão (suite cheia 171 pass).

## 2026-05-13 — F5.3 fechada com 4 commits + rebase

**Contexto:** F5.3 fechou o ciclo do projeto (criação → reports → encerramento estruturado, spec v3.1 §10.4). Endereçou o item D do P2 da auditoria de conformidade — endpoint `POST /projects/{id}/close` + UI + `ProjectRetrospective` com 4 campos.

**Decisão:** estrutura final em 5 commits no histórico (4 commits + 1 rebase dividindo o do endpoint):

| # | Hash | Tipo | Conteúdo |
|---|---|---|---|
| 1 | `fe93d50` | feat | Modelo drop+recreate + migration 0016 + `.coveragerc` |
| 2a | `4de0188` | fix | auth/register case-bug (isolado em commit dedicado) |
| 2b | `93bf7bc` | feat | Endpoint POST /close + GET retrospective + cascade Q4 |
| 3 | `bf5b97f` | feat | Frontend rota /encerramento + render pós-CLOSED + GET /risks |
| 4 | `(este)` | test+docs | 7 testes /risks + spec Playwright + conformidade + progresso |

**Métricas finais:** pytest 150 → 178 (+28 testes); vitest 84 → 95 (+11 testes); cobertura backend total 87% (com `.coveragerc` real); `projects.py` 91%. Suite cheia 178 pass / 1 skip / 0 fail.

**Consequência:** ciclo do projeto fica completo (criação → reports → encerramento estruturado) — pré-requisito explícito para F5.5 (Agente de Inteligência Cruzada consome retrospectivas). 4 débitos P3 do F5.3 registrados em `conformidade-v3.1.md`; débito F5.2.d **resolvido** (cobertura async via `.coveragerc`); débito F5.3.c **resolvido** no commit 4. Bug dormente descoberto e corrigido em commit isolado preserva auditoria. Aprendizado de cobertura real (87%, não 72%) anotado em `fase-5-progresso.md` para que métricas históricas sejam interpretadas com contexto.

## 2026-05-13 — F5.4 fechada com 4 commits

**Contexto:** F5.4 implementa o Modo de Report Assistido por IA (spec v3.1 §10.2). Endereça o item C do P2 da auditoria de conformidade — pré-popular novo report com base no anterior.

**Decisão:** estrutura final em 4 commits sequenciais:

| # | Hash | Tipo | Conteúdo |
|---|---|---|---|
| 1 | `d90eef5` | feat | Flag `is_prepopulated` + migration 0017 + service `prepopulate_report` |
| 2 | `5e5d258` | feat | Endpoint `POST /projects/{id}/reports/prepopulate` + UI radio escolha de modo |
| 3 | `9dc3a65` | feat | Badge "Do report anterior" + auto-zero da flag em PATCH via snapshot |
| 4 | `(este)` | test+docs | Modal 409 com link + Playwright spec + conformidade + progresso |

Implementa pré-população do report cumprindo **80% da spec §10.2** (herança de Risks/Pendings/DeliveryProgress placeholders). **Sugestões textuais da IA (§10.2 ponto 3) ficam para quando F2.6/F5.5 trouxer agente real** — débito F5.4.X registrado.

**Métricas finais:** pytest 178 → 195 (+17 testes); vitest 95 → 104 (+9 testes); cobertura backend total 88% (estável). Suite cheia 195 pass / 1 skip / 0 fail.

**Consequência:** GP economiza tempo significativo a cada novo report — riscos abertos, pendências em aberto e entregas no prazo do período já vêm pré-preenchidas com badge visual "Do report anterior". Backend zera a flag automaticamente quando o GP edita, mantendo a auditoria clean. F5.4.W (match-by-description em PATCH), F5.4.X (sugestões IA), F5.4.Y (botão criar plano vinculado), F5.4.Z (limitação Vitest em Tabs) e PNGs Playwright pendentes registrados como débitos P3. Nenhum bloqueia release.

## 2026-05-13 — F5.6a / Worker real é processo separado; stub asyncio preservado (decisões B-α/β/γ)

**Contexto:** F5.6a constrói o worker real (consumidor da fila Redis `jobs.agent`) que fechará — junto com F5.6b — o débito K (F2.6 worker real + F2.8 smoke). O briefing inicial sugeria "substituir `worker_stub.py` por `worker_real.py`", mas o inventário do início da sub-fase revelou três coisas:

1. `backend/app/services/worker_stub.py` é um **stub asyncio in-process** (não consome Redis), controlado por `STUB_WORKER_ENABLED` — é fallback de **desenvolvimento**, não o lugar onde o worker real vive.
2. `jump_agent_runner/` (lib desde F1) já oferece `AgentRunner` com fallback Claude↔Codex, `ClaudeProvider`/`CodexProvider`, `WSLTmuxBroker`, `ArtifactValidator` e `Observer` — o worker apenas **instancia** essa máquina, não duplica nada.
3. `worker/pyproject.toml` já declara dependências e entrypoint `jump-worker = worker.main:main`, mas `worker/worker/main.py` ainda **não existe**. Esse é o coração do F5.6a.

Três decisões pontuais sobre o escopo do worker real (B-α/β/γ) também precisaram ser resolvidas antes do código.

**Decisão:**

1. **`worker_stub.py` NÃO é substituído nem renomeado.** Continua existindo no backend como fallback dev controlado por `STUB_WORKER_ENABLED`. O worker real é processo separado em `worker/worker/main.py`, consome `jobs.agent` do Redis e reporta via `POST /internal/agent-results/{run_id}` (HMAC). Em produção, `STUB_WORKER_ENABLED=false` desliga o stub e a publicação no Redis vira o caminho ativo. Em dev local sem worker rodando, o stub mantém o fluxo do frontend honesto.

2. **B-α — Status `RUNNING` durante execução: (a) não muda nada.** O endpoint atual só aceita estado terminal (DONE/FAILED). Heartbeat periódico do worker já dá observability suficiente sobre "worker vivo + processando". Adicionar `phase=start|complete` no callback exigiria mudança no schema/endpoint que não estava no escopo do F5.6a. Quando alguém pedir visibilidade granular do estado intermediário, reabrir essa decisão — provavelmente em F5.9 (pré-deploy) ou no primeiro feedback do PMO no piloto.

3. **B-β — Construção do prompt: (a) stub mínimo de prompt em F5.6a.** `worker/worker/prompt_builder.py` retorna template hardcoded por `task_type` ("você é o agente leitor de propostas / análise de relatório / padrão de portfólio"). O prompt versionado real (`proposal_reader_v1.md`) entra no fluxo só em F5.6b, junto com o smoke F2.8 que valida a aderência. Razão: prompt real exige acoplamento com `schema_hint` e com download de input (B-γ) — empacotar tudo em F5.6a estouraria o orçamento da sub-fase.

4. **B-γ — Download de input (PDF da proposta): (a) F5.6a roda jobs sintéticos.** Se o payload tiver `input_files=[]`, o worker invoca claude só com o prompt — suficiente para testar o ciclo Redis→runner→callback→AgentRunLog. Download via boto3 do R2 (lib já em deps) entra em F5.6b, junto com o smoke real contra a proposta Bradesco. F5.6a foca em provar que o **transporte** funciona; F5.6b prova que a **extração** funciona.

**Consequência:** F5.6a fica enxuto e isolado de dependências externas (R2, prompt versionado, proposta real). Todos os testes pytest do worker podem mockar `AgentRunner` integralmente e validar o ciclo de mensageria + HMAC + heartbeat — não há claude/codex sendo chamado em teste automatizado. Risco residual: F5.6a pode passar verde e F5.6b descobrir bugs na borda runner↔worker que só aparecem com proposta real (longo timeout, falha de download, prompt rejeitado pelo validator). Mitigação: F5.6b vai exercitar essa borda em smoke explícito; se descobrir gap, reabre F5.6a parcialmente para o ajuste pontual.

Débito K em `docs/conformidade-v3.1.md` passa a estar **parcialmente endereçado** ao fim de F5.6a (F2.6 worker real cumprido; F2.8 smoke ainda aberto). F5.6b fecha o débito K completo. ADR registra também a mudança no `worker/scripts/setup-windows.ps1` para suportar essa arquitetura: `systemd=true` no `/etc/wsl.conf`, Node 20 LTS via NodeSource, ordem de `PATH` priorizando `~/.npm-global/bin` sobre `/mnt/c/.../npm` — sem essas três correções, `claude` continua resolvendo pro mount Windows e cai na armadilha do ADR `2026-05-11 — F2.8 adiado`.

## 2026-05-13 — F5.6a fechada (worker real entrega pipeline; smoke F2.8 segue para F5.6b)

**Contexto:** F5.6a era o pacote prático para destravar o ADR `2026-05-11 — F2.8 adiado para F5`. Inventário ativo do início da sub-fase mostrou que o `jump_agent_runner` (lib desde F1) já tinha ~80% da máquina pronta (AgentRunner, providers Claude/Codex, broker WSL+tmux, routes headless, ArtifactValidator, Observer, CLI smoke) e que o backend já oferecia `POST /internal/agent-results/{run_id}` com HMAC + `WorkerHeartbeat`. O que faltava era (a) o entrypoint do processo em `worker/worker/main.py`, (b) atualizações no `setup-windows.ps1` que destravassem o bug de `claude` resolvendo via mount Windows. Decisões B-α/β/γ resolvidas com (a)/(a)/(a) para manter F5.6a enxuto.

**Decisão:** estrutura final em 4 commits sequenciais:

| # | Hash | Tipo | Conteúdo |
|---|---|---|---|
| 1 | `0cb9ff9` | docs | Runbook `setup-worker-wsl.md` (12 passos idempotentes + 6 troubleshootings + 4 anexos) + ADR worker real agrupando decisões B-α/β/γ |
| 2 | `365e0d7` | chore | `setup-windows.ps1` reescrito idempotente (systemd em `/etc/wsl.conf`, Node 20 LTS via NodeSource, PATH `~/.npm-global/bin` precede mount Windows, relatório colorido final por componente, tmux preserva sessões existentes) + seção "Como rodar o worker em dev" em `dev_notes.md` |
| 3 | `797785f` | feat(worker) | 6 módulos novos em `worker/worker/` — `config.py` (Pydantic Settings), `hmac_signer.py` (espelha backend), `http_client.py` (retry tenacity em 5xx/408/network), `heartbeat.py` (task asyncio paralela), `prompt_builder.py` (stub B-β), `main.py` (BRPOP→Runner→callback HMAC→dead-letter→cleanup) |
| 4 | `(este)` | test+docs | 27 testes pytest com 82% cobertura, `.env.example`, `.coveragerc` (sem greenlet — worker é puro asyncio), atualização `conformidade-v3.1.md` (débito K → parcial; F5.6a.X e F5.6a.Y registrados) + `fase-5-progresso.md` |

**Métricas finais:** pytest worker 0 → **27** (pacote novo, cobertura 82%, gate ≥70% folgado); pytest backend e vitest frontend inalterados (F5.6a não toca código de produto fora de `worker/`). Suite cheia do monorepo: 195 backend + 27 worker + 104 vitest, sem regressão. Tempo de execução dos testes do worker: 17s.

**Consequência:** débito K (`F2.8 — smoke real do agente leitor`) passa a estar **parcialmente endereçado** — F2.6 (worker real) pronto, validado por pipeline + retry + dead-letter + heartbeat. F5.6b fecha o débito K completo (carrega `proposal_reader_v1.md`, baixa proposta do R2 via boto3, invoca claude nativo, compara com `bradesco_sas_databricks.expected.json`, gera `docs/f28-bradesco-baseline-quality.md`). F5.6b também força a decisão **F5.6a.Y** (onde o `jump-worker` roda — Windows host com wrapper para `wsl.exe`, ou Python dentro do WSL Linux com claude no PATH nativo). Próxima sub-fase pode ser F5.6b OU pular para F5.5 (inteligência cruzada — não exige smoke validado, só worker funcional, que já temos).

## 2026-05-14 — F5.6a / Bug `--bare` desabilita OAuth no Claude Code v2.1.x (fecha causa raiz do ADR 2026-05-11)

**Contexto:** durante a execução do setup F5.6a, com `claude` instalado nativamente no Linux do WSL (`~/.npm-global/bin/claude`) e OAuth login completado com sucesso via TUI (`claude /login` autenticou conta `christopher.tominaga@jumplabel.com.br` na Team), a invocação headless `claude -p '...' --bare --output-format json` continuou retornando o mesmo erro do ADR `2026-05-11 — F2.8 adiado`:

```
"Not logged in · Please run /login"
```

Ou seja, o diagnóstico original do 2026-05-11 (atribuído a "mount cross-OS errático") era **incompleto**. Mesmo com tudo no Linux nativo, o headless falhava.

**Decisão / Diagnóstico:** o `claude --help` do v2.1.141 documenta literalmente:

```
--bare    Minimal mode: skip hooks, LSP, plugin sync, attribution,
          auto-memory, background prefetches, keychain reads, and
          CLAUDE.md auto-discovery. Sets CLAUDE_CODE_SIMPLE=1.
          Anthropic auth is strictly ANTHROPIC_API_KEY or
          apiKeyHelper via --settings (OAuth and keychain are
          never read).
```

`--bare` no v2.1.x passou a **estritamente exigir API key** e desabilitar OAuth/keychain. Versões anteriores (quando o `jump_agent_runner` foi escrito em F1) aceitavam OAuth com `--bare`. Spec proíbe API key (modo shadow no piloto Bradesco depende de Team subscription via OAuth, não billing API).

**Mudança:** commit `4c22e53` removeu `--bare` de:
- `jump_agent_runner/routes/claude_headless.py` (cmd headless principal)
- `jump_agent_runner/broker/wsl_tmux.py` (probe `is_logged_in`)

Os comportamentos úteis do `--bare` (skip hooks, LSP, plugin sync, CLAUDE.md auto-discovery) já são implícitos em `-p` (print mode non-interactive). Não há regressão. Suite cheia do `jump_agent_runner`: 71 passed.

Smoke manual pós-fix (executado em F5.6a):

```bash
claude -p 'responda apenas: ok' --output-format json
# {"is_error": false, "result": "ok", ...}
```

**Consequência:** o motivo técnico do F2.8 ter sido adiado (`2026-05-11 — F2.8 adiado`) está **fechado**. F5.6b agora pode invocar o agente leitor real contra a proposta Bradesco sem precisar de API key — basta o OAuth Team. Adicionalmente, descobriu-se que `bash -lc` (login shell, usado por subprocess Python e `wsl -- <cmd>`) ignora `~/.bashrc` — exige PATH em `~/.profile`. Commit `adf41b7` ajustou o `setup-windows.ps1` para escrever em ambos.

**Lição operacional:** flags de CLIs externos podem mudar semântica entre minor versions. Pin de versão do `@anthropic-ai/claude-code` (atualmente `npm install -g` sem pin) seria mais seguro pro setup do worker em piloto, ao custo de não receber bugfixes automaticamente. Decisão aberta para F5.6b/F5.9.

## 2026-05-14 — F5.6b / F2.8 fechado: agente leitor v1 valida contra proposta Bradesco

**Contexto:** F5.6b era o pacote final do débito K (aberto desde ADR `2026-05-11 — F2.8 adiado para F5`). Após F5.6a destravar os pré-requisitos (worker real + diagnóstico do `--bare`), faltava (1) rodar o agente real contra a proposta gold-standard com o prompt versionado `proposal_reader_v1.md`, (2) comparar o output contra `bradesco_sas_databricks.expected.json`, (3) decidir se o agente pode operar em modo automático no piloto. Decisão arquitetural pendente: **F5.6a.Y — onde o `jump-worker` (e o smoke) rodam: Windows host invocando `wsl.exe -- claude` ou Python dentro do WSL Linux com claude no PATH nativo?**

**Decisão:** estrutura final em 4 commits sequenciais:

| # | Hash | Tipo | Conteúdo |
|---|---|---|---|
| 1 | `177e5ee` | chore | **Resolve F5.6a.Y**: Python venv via `uv` (instalado por `pip install --user`, não `curl|sh` — mesma decisão de F5.6a.X) em `~/.jump-runner/.venv-worker`. `setup-windows.ps1` passos 3.11–3.14 idempotentes. `wsl --cd $repoRootWsl --` para que `$PWD` aponte para a raiz do monorepo. |
| 2 | `84f5e72` | feat | `scripts/f28_smoke_bradesco.py` — invoca `AgentRunner(ClaudeProvider, CodexProvider)` direto contra texto pré-extraído da proposta Bradesco (Q2=b) com prompt `proposal_reader_v1.md`. Salva artefato + metadata em `~/.jump-runner/f28-bradesco/`. |
| 3 | `92ffb61` | feat | `scripts/f28_compare_bradesco.py` (recall simples + recall ponderado por criticidade) + `f28_show_bradesco_output.py` (helper de debug) + `docs/f28-bradesco-baseline-quality.md` (relatório completo com decisão operacional dual). |
| 4 | `(este)` | docs | ADR de fechamento, atualização `conformidade-v3.1.md` (K marcado ✅), `fase-5-progresso.md` (seção F5.6b completa), memória `project_jump_gp_portal.md`. |

**Resultado do smoke (run `f28-bradesco-1778780537`):**

- 159.2s no Claude headless (1 tentativa, sem fallback).
- `phases` 100% (4/4), `deliverables` 100% (21/21), `project` 90.9% (10/11).
- `key_premises` 0% strict / 33% para `out_of_scope` — artefato do Jaccard de palavras para sinônimos PT-BR (16 e 17 extras semanticamente válidos respectivamente).
- **Recall simples 64.8% (SHADOW). Recall ponderado por criticidade 81.5% (PASS).**

**Decisão operacional final (aprovada por Christopher Tominaga):**

- **PASS técnico** — agente leitor v1 entra em produção no piloto.
- **SHADOW na semana 1** — spec v3.1 §1.5 já prevê; GP audita o primeiro baseline real.
- **Upgrade condicional para AUTOMÁTICO na semana 2+** — critério binário: se GP editar pouco/nada em premises/oos do primeiro baseline, agente promove. Se editar muito, abre ciclo de iteração para `proposal_reader_v1.1.md`.

**Decisões refinadas durante a execução:**

- **Q1 (F5.6a.Y) = (a) WSL Linux**: refactor de `ClaudeHeadlessRoute` para invocar `wsl.exe` seria menos aderente à spec original do `02_jump_agent_runner_spec.md §6.1`. Manter Python no WSL é menos invasivo. Resolve simultaneamente o problema de mount cross-OS (`/mnt/c/.../npm/claude` vs `~/.npm-global/bin/claude`) que reapareceria se Python rodasse no Windows host.
- **Q2 = (b) `.txt` pré-extraído**: isola "agente leitor" de "extração de PDF". Download R2 + `pypdf` no fly fica para F5.6c/F5.9 — não bloqueia o piloto onde o worker REAL (não o smoke) baixa o PDF.
- **Q3 evoluído**: começou como "strict" (decisão original do briefing). Quando o número simples ficou em SHADOW mas inspeção visual mostrou que era artefato do Jaccard, foi adicionada **métrica ponderada por criticidade do campo** como segundo veredito. Reportar AS DUAS dá ao operador o sinal correto sem esconder a fragilidade da heurística.

**Consequência:** débito K **FECHADO**. Bug F2.8 do ADR `2026-05-11` resolvido em duas frentes complementares (bug `--bare` + Python no Linux). F5.6 (a+b) virou o **destravamento técnico mais importante de F5** — não só fechou o débito mas também consolidou o **ambiente de desenvolvimento worker** que servirá F5.5, F5.7 e F5.9. F5.6a.Y resolvida. Próximas sub-fases: F5.7 (LGPD, DPO Christopher), F5.5 (inteligência cruzada, paralelizável), F5.8 (export, independente), F5.9 (deploy + v3.2). Caminho crítico para piloto Bradesco está claro.

**Riscos residuais conhecidos (documentados em `docs/f28-bradesco-baseline-quality.md`):** (1) `project.estimated_capacity_per_sprint_hours` não extraído (trivialmente derivável); (2) 2 itens de `out_of_scope` do expected não capturados — risco controlado pelo SHADOW; (3) Jaccard de palavras é fraco para sinônimos — substituir por embedding similarity local em hardening futuro (F5.9 ou F6).

**Riscos arquiteturais decididos (não residuais):**
- **CodexProvider permanece como fallback configurado mas sem login efetivo** — URL do installer oficial retornou não-200 em 2026-05-14 (F5.6a.X pegou cedo). Plano B3 do runbook em vigor: rodar só com Claude. `AgentRunner` configurado a cair para Codex se Claude falhar, mas Codex reportará `BROKER_UNAVAILABLE` cedo. Operacionalmente aceitável.
