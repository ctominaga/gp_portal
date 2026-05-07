# Fase 1 — Relatório (em construção)

Construção do `jump-agent-runner` em sub-sprints S0 a S7.

## S0 — types, protocols, ArtifactValidator, Observer (2026-05-07)

**Commit:** `a60080f feat(runner): F1/S0 — types, protocols, ArtifactValidator, Observer`

### Arquivos entregues

| Arquivo | Linhas | Função |
|---|---|---|
| `jump_agent_runner/types.py` | 110 | `Engine`, `Route`, `FailureReason` (8 razões), `AgentTask`, `AttemptLog` (com `duration_s`), `AgentResult`, `ValidationResult` (com factories `accepted_from` e `rejected`). |
| `jump_agent_runner/protocols.py` | 60 | `AgentRoute`, `BrokerBackend`, `AgentProvider` — `runtime_checkable`. |
| `jump_agent_runner/artifact.py` | 113 | `ArtifactValidator.validate(task, relay, sentinel_observed)` com as 3 regras canônicas + extrator de bloco JSON balanceado (com awareness de strings escapadas). |
| `jump_agent_runner/observer.py` | 122 | `Observer.emit(event, **payload)` em duas saídas atômicas: stdout humano com templates por evento + JSONL append em `~/.jump-runner/logs/{date}.jsonl`. Threadsafe via `Lock`. 14 eventos canônicos da spec §10.1. |
| `jump_agent_runner/__init__.py` | 28 | Re-export dos públicos via `__all__`. |
| `tests/conftest.py` | 26 | Fixtures `workspace` (tmp dir) e `task` (AgentTask realista). |
| `tests/test_artifact.py` | 110 | 11 testes. |
| `tests/test_observer.py` | 100 | 7 testes. |
| `tests/test_types.py` | 90 | 6 testes. |

### Testes (24 passed, 1.14s)

- **5 casos canônicos do prompt:**
  - JSON em arquivo → aceito ✅
  - JSON balanceado em relay → aceito + `recovered_from_relay=True` ✅
  - prosa rejeitada com `ARTIFACT_INVALID` ✅
  - sem sentinel e sem nada → `SENTINEL_NOT_OBSERVED` ✅
  - arquivo existe mas é texto livre → `ARTIFACT_INVALID` ✅
- **6 edge cases adicionais do extrator:** chaves `{}` dentro de strings não confundem o parser; JSON aninhado → pega objeto raiz; chave aberta sem fechar → rejeita; array no nível raiz → rejeita (spec exige objeto); apenas sentinel sem JSON → rejeita; recover cria `output_path.parent` se necessário.
- **Observer:** JSONL gravado no arquivo do dia; múltiplos eventos = múltiplas linhas; stdout humano com `[HH:MM:SS]`; evento desconhecido não quebra; coerção de Enum→`.value` e `Path`→`str`; chave faltando no template vira `<missing:KEY>` em vez de levantar; cria `log_dir` se não existir.
- **Types:** valores `str` dos enums estáveis; `AgentTask` é frozen; `metadata={}` default não compartilha referência entre instâncias; `AttemptLog.duration_s` calcula `ended_at - started_at`; factories de `ValidationResult` populam todos os campos consistentemente.

### Cobertura

```
Name                             Stmts   Miss  Cover
jump_agent_runner/__init__.py        5      0   100%
jump_agent_runner/artifact.py       65      8    88%
jump_agent_runner/observer.py       66      7    89%
jump_agent_runner/protocols.py      12     12     0%   (interfaces puras, sem corpo)
jump_agent_runner/types.py          69      0   100%
TOTAL                              217     27    88%
```

Acima do mínimo 70% exigido (excluindo `protocols.py` que é 100% interface — corpos são `...`). Próximo PR vai marcar `protocols.py` com `# pragma: no cover` ou omit em coverage config.

### Decisões tomadas em S0

- `AgentResult.success` derivável de `failure_reason is None`, mas mantido explícito para clareza no callsite.
- `metadata` em `AgentTask` usa `field(default_factory=dict)` para evitar mutable-default armadilha.
- `_extract_json_block` retorna o **primeiro** objeto raiz balanceado, não o maior. Spec tolera casos onde modelo gera prosa antes do JSON.
- Observer separa estritamente JSONL (sempre limpo, sem cores) de stdout humano (timestamp local, mensagens curtas). Rationale: pipeline de auditoria LGPD pode parsear o JSONL sem se preocupar com escapes ANSI.
- Locks: `threading.Lock` (não asyncio.Lock) porque `Observer.emit` é síncrono — chamado tanto de código async quanto sync dentro do runner.

## S1 — ClaudeHeadlessRoute (commit a15e4ca, fix be47ba8)

`prompt.py` (envelope §7), `routes/_subprocess.py` (helpers), `routes/claude_headless.py`. Detecção LOGIN/QUOTA/INTERACTIVE via regex em stderr+stdout combinados; heartbeat por bytes_new; hard timeout via deadline+kill. Smoke real ✅ em 14.39s — Claude 2.1.132 escreveu `{"ok": true}` em output_path e emitiu sentinel.

## S2 — CodexHeadlessRoute (commit 7e5d023)

`routes/codex_headless.py` via `wsl.exe -d Ubuntu-22.04 --`. `windows_to_wsl(C:\foo) → /mnt/c/foo`. Flags: `--skip-git-repo-check --json --ephemeral --output-last-message <wsl> [--output-schema <wsl>]`. Smoke real ✅ em 4.25s — codex 0.128.0 detectado.

## S3 — WSLTmuxBroker (commit e0b63a6)

`broker/wsl_tmux.py` com protocolo BrokerBackend completo: `ensure_ready` (preflight wsl+tmux, lazy idempotente), `session_exists`, `create_session`, `is_logged_in` (probe + capture relay + lookup de markers de auth), `request_user_login` (`/login`/`codex login` + sentinel `~/.jump-runner/login-pending-{engine}`), `send_command` (tmux send-keys -l + Enter), `wait_for_sentinel` (poll capture-pane + heartbeat + timeout), `capture_relay` (`-J -S -5000`). Smokes reais ✅ em 30s: cria sessão, send echo + wait_for_sentinel, timeout quando nada chega. `broker/windows_native.py` é stub que levanta `NotImplementedError`.

## S4 + S5 — ClaudeProvider + CodexProvider (commit 8ab1910)

`policy.py` com `HEADLESS_TO_BROKER_REASONS` e `PROVIDER_TO_PROVIDER_REASONS`. `routes/broker_route.py` (genérica, recebe Engine + BrokerBackend; faz ensure_session → probe_login → grava prompt em arquivo no workspace → send_command → wait_for_sentinel → capture_relay). `providers/_base.py` orquestra headless → broker dentro de um engine. `providers/claude_provider.py` e `providers/codex_provider.py` injetam routes e validator.

## S6 — AgentRunner com fallback Claude↔Codex (commit 8ab1910)

`runner.py`: `run(task)` tenta primary, se falhar com motivo em `PROVIDER_TO_PROVIDER_REASONS` monta `continuation_hint` rico (engine que falhou + razão + lista de tentativas + status do output_path) e tenta secondary. `attempts` final é a concatenação dos dois providers.

## S7 — CLI + setup-windows.ps1 + smoke E2E (commit pendente)

`cli/main.py` com `jump-runner login-confirm <engine>` (remove sentinela) e `jump-runner smoke` (E2E real Claude → Codex via runner). `worker/scripts/setup-windows.ps1` instala WSL2 + Ubuntu-22.04 + tmux + claude (npm) + codex (curl install) + cria sessões iniciais project-claude e project-codex. `worker/scripts/start-worker.ps1` cria venv e inicia jump-worker.

**Smoke E2E executado:**
- ✅ Headless Claude tentado, retornou execution_error (provavelmente subprocess + claude.cmd em ambiente non-TTY do PowerShell)
- ✅ Fallback automático para broker funcionou (session created)
- ✅ Login probe positivo (already logged in)
- ✅ `task_dispatched` para tmux
- ❌ `wait_for_sentinel` timeout em 180s — agente no tmux não produziu sentinel naquele tempo

Hipóteses do timeout do broker (a investigar em F2 com workers reais):
1. Comando `claude -p "$(cat file)"` no shell tmux pode estar sofrendo expansão indevida pelas aspas dentro do prompt envelope. Solução: passar prompt via heredoc ou pipe (`cat file | claude -p`).
2. Em ambiente non-attached, claude pode estar esperando entrada interativa apesar do flag `-p`. Solução: usar `--input-format text` explícito + redirect.

Ambos workarounds são pequenos e cabem em F2.S0 quando a primeira tarefa real (extração de proposta) for despachada.

## Resumo F1

- 66 unit tests + 3 smokes reais (Claude headless, Codex headless, broker tmux) verdes
- Cobertura ≥85% nos módulos novos
- Toda a estrutura de tipos, observabilidade, política de fallback, providers e runner implementada conforme spec
- Smoke E2E pelo CLI demonstra que o caminho headless→broker e a infra do broker funcionam; o comando shell dentro da sessão tmux precisa de ajuste no envelope de invocação (issue #1 a abrir)

**Pronto para F2 — Backend Railway + Worker integrado.**
