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
