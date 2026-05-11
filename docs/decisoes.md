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
