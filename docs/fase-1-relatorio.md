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

### Próximo: S1 — ClaudeHeadlessRoute

S1 (1d) entrega `routes/claude_headless.py` com `is_available` e `execute`, wrapping de prompt conforme spec §7, detecção de `LOGIN_REQUIRED` / `QUOTA_EXCEEDED` / `EXECUTION_ERROR`, heartbeat periódico, hard timeout via `asyncio.wait_for`, e mitigação para issue de stdin grande (input vai pra arquivo). Smoke test real chamará `claude -p` no terminal atual (você confirmou que está disponível).

Pronto para começar S1?
