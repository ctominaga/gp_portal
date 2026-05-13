# Notas técnicas de desenvolvimento

Documento curto, sempre atualizado, com convenções e armadilhas que vale
internalizar. ADRs vão em `decisoes.md`; aqui ficam regras práticas do
dia-a-dia.

## Convenções de enum no projeto

### SAEnum sem `values_callable` persiste `e.name` (UPPERCASE), não `e.value`

Todos os enums Python do projeto herdam de `(str, enum.Enum)` e são mapeados
via `SAEnum(EnumClass, name="...", native_enum=False)`. Sem o argumento
`values_callable`, SQLAlchemy persiste o **nome** do membro do enum no banco
(UPPERCASE), não o valor:

```python
class BaselineStatus(str, enum.Enum):
    DRAFT = "draft"        # ← value (não é o que vai pro banco)
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"

# No banco, a coluna 'status' guarda: 'DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED'
# (os NAMES). Leitura via ORM faz o lookup reverso name → membro Python.
```

**Implicação para migrations:** todo SQL literal que mexer em coluna de enum
deve usar o NAME (UPPERCASE), não o value (lowercase):

```sql
-- ✅ Correto
UPDATE risks SET status = 'IDENTIFIED' WHERE ...;
UPDATE scope_changes SET change_type = 'ADDED' WHERE description LIKE 'Adicionado:%';

-- ❌ Errado — ORM falhará ao ler com LookupError
UPDATE risks SET status = 'identified' WHERE ...;
```

**Enums afetados (todos do projeto):**

| Arquivo | Enum |
|---|---|
| `app/models/domain.py` | `ProjectStatus`, `ProposalStatus`, `BaselineStatus`, `DeliverableComplexity`, `DeliverableType`, `DeliverableCategory`, `DeliverableStatus`, `ReportStatus`, `RAGStatus`, `ProgressStatus`, `RiskLevel`, `RiskProbability`, `RiskImpact`, `RiskStatus`, `ActionPlanStatus`, `PendingItemStatus`, `InsightScope`, `ScopeChangeStatus`, `ScopeChangeType`, `TaskType`, `AgentRunStatus`, `ApprovalStage`, `ApprovalDecision`, `DPRequestType`, `DPRequestStatus` |
| `app/models/user.py` | `Role` |

**Reescrita via ORM (não SQL literal):** continue passando o membro Python
direto — SQLAlchemy lida com a serialização:

```python
risk.status = RiskStatus.IDENTIFIED   # Python → 'IDENTIFIED' no banco
sc.change_type = ScopeChangeType.ADDED  # idem
```

**Inconsistência conhecida:** migrations antigas (0003, etc.) usam
`server_default="active"` (lowercase). Não causa bug porque server_defaults
só disparam em INSERT sem valor explícito, e código Python sempre passa o
membro do enum (mesmo no commit do ORM). Fica como dívida cosmética; só vira
problema se alguém fizer `INSERT INTO ... DEFAULT VALUES` direto via SQL.

**Origem:** descoberto em F5.2 commit 1 (ADR `2026-05-12 — F5.2 / Convenção
SAEnum`). Inspeção empírica feita com `SAEnum._object_lookup`.

## Testes que tocam o banco usam SQLite + `Base.metadata.create_all`

`conftest.py` (`backend/tests/conftest.py`) cria fresh DB com
`create_all`, não roda Alembic. Implicações:

- **Migrations não são exercitadas pela suite de testes regular.** Para
  testar lógica de backfill ou DDL específico de uma migration, extraia
  a função de backfill como helper público no módulo da migration
  (vide `0014_scope_change_refactor.py::run_backfill`) e importe via
  `importlib.util.spec_from_file_location` no teste. O nome do arquivo
  começa com dígito → import normal não funciona.
- **Cobertura de função async pode ser subreportada.** `pytest-cov` sem
  `concurrency = ["thread", "greenlet"]` na config nem sempre instrumenta
  o trace dentro de event loops asyncio. Indicador: teste passa (verde),
  endpoint claramente exercitado, mas as linhas da função aparecem como
  "não cobertas" no relatório. Verificar comportamento manualmente; não
  confiar 100% no número de cobertura raw para funções async.

## Convenção de teste pós-mutação via HTTP

Quando o teste faz `await client.post(...)` que muta estado no banco e
depois precisa validar, NÃO use `db_session.get()` ou
`db_session.refresh()` diretamente — a sessão de teste com `StaticPool`
mantém cache stale (identity map) após o request, e `expire_all()` nem
sempre resolve. Padrão: validar via outro `await client.get(...)`.

```python
# ✅ Padrão
r = await client.post(f"/baselines/{b.id}/transition", json={...})
assert r.status_code == 200
r_check = await client.get(f"/baselines/{b.id}", headers=auth)
assert r_check.json()["status"] == "active"

# ❌ Frágil
await client.post(...)
fresh = await db_session.get(Baseline, b.id)  # cache stale
```

## Como rodar o worker em dev (F5.6a)

Pré-requisitos:

1. `setup-windows.ps1` rodou sem falhas (ver relatório colorido no fim da execução).
2. `claude /login` e `codex login` feitos dentro dos `tmux project-claude` / `project-codex`. Verificar com `wsl -d Ubuntu-22.04 -- bash -lc "[ -f ~/.claude/.credentials.json ] && echo OK"`.
3. Redis local rodando. `docker-compose up redis -d` na raiz do `jump-report/` resolve.
4. Backend rodando (FastAPI em `:8000`) — o worker faz callback HMAC para `POST /internal/agent-results/{run_id}` e `POST /internal/worker-heartbeat`.

Boot do worker (disponível após Commit 3 do F5.6a):

```powershell
# Na raiz jump-report/
cd worker
.\scripts\start-worker.ps1
# Primeira execução: cria .venv, instala jump_agent_runner editable + worker editable, dispara jump-worker.
# Execuções subsequentes: só dispara jump-worker.exe direto.
```

O processo `jump-worker` fica em foreground consumindo `jobs.agent` do Redis via BRPOP. `Ctrl+C` encerra com SIGINT (drena job atual, fecha graceful).

Para validar que o setup completo funciona sem precisar enfileirar via UI:

```powershell
# Smoke trivial — invoca claude direto via jump_agent_runner CLI, sem passar por worker/Redis:
.\.venv\Scripts\jump-runner.exe smoke
```

Logs:

- `~/.jump-runner/logs/{YYYY-MM-DD}.jsonl` (Linux) — eventos estruturados do `Observer` (cada run produz uma linha JSON por evento).
- `stderr` do `jump-worker` — eventos do próprio worker (BRPOP, callback, heartbeat).
- Tabela `worker_heartbeats` no Postgres — última batida + jobs do dia. Útil para health check operacional.

Variáveis de ambiente do worker ficam em `worker/.env` (copiar de `worker/.env.example`). Reaproveitam `WORKER_SHARED_SECRET` e `WORKER_HMAC_KEY` do `.env` da raiz — o backend valida com a MESMA chave, então tem que bater.

## Mocks Playwright usam URL absoluta do API server

Vide ADR `2026-05-08 — F4 / Mocks Playwright`. Resumo: `page.route()` com
glob amplo `**/portfolio` casa também a navegação Next (`/pmo/portfolio`),
fazendo o browser exibir JSON cru. Sempre use a URL absoluta do API server:

```ts
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
await page.route(`${API}/portfolio`, ...);
```
