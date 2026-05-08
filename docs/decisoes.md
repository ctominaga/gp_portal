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

## 2026-05-08 — F4 / Mocks Playwright usam URL absoluta do API server, não glob amplo

**Contexto:** durante geração de screenshots do F4, o spec usava `page.route("**/portfolio", ...)`. O glob `**/portfolio` casa qualquer URL terminada em `/portfolio` — então tanto a chamada da API (`http://localhost:8000/portfolio`) quanto a navegação Next (`http://localhost:3100/pmo/portfolio`) eram interceptadas e devolviam JSON. O browser exibia o JSON cru com pretty-print, e o `waitForSelector("text=SAS→Databricks")` "passava" porque a string aparece tanto no `project_name` do JSON quanto na UI esperada. O PNG comitado era do JSON, não da UI.

**Decisão:** todo `page.route()` em specs Playwright deve usar URL absoluta com escopo do API server (constante `API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`), não glob amplo `**/...`. Aplicado preventivamente também em `screenshots.spec.ts` (F3.5), que estava OK por sorte de naming (frontend usa `/projetos`, backend `/projects`) mas era frágil.

**Consequência:** mocks deixam de competir com o roteamento do Next. Adicionado helper `assertReactUiRendered(page)` no spec F4 (verifica >=1 `<h1>`) chamado antes de cada `page.screenshot()`, com teste negativo que injeta o bug e confirma que o helper rejeita. Próximos specs Playwright que usem `page.route()` devem seguir essa convenção.
