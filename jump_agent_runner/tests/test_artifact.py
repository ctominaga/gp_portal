"""Testes do ArtifactValidator — 5 casos canônicos da spec."""
from __future__ import annotations

import json
from pathlib import Path

from jump_agent_runner.artifact import ArtifactValidator
from jump_agent_runner.types import AgentTask, FailureReason


def test_json_em_arquivo_aceito(task: AgentTask) -> None:
    task.output_path.write_text(json.dumps({"ok": True, "n": 7}), encoding="utf-8")
    result = ArtifactValidator().validate(task, relay="qualquer prosa", sentinel_observed=True)

    assert result.accepted is True
    assert result.recovered_from_relay is False
    assert result.artifact_path == task.output_path
    assert result.artifact_data == {"ok": True, "n": 7}
    assert result.failure_reason is None


def test_json_balanceado_em_relay_aceito(task: AgentTask) -> None:
    relay = (
        "Aqui vai meu trabalho:\n"
        "```json\n"
        '{"name": "bradesco", "phases": [{"id": 1}, {"id": 2}]}\n'
        "```\n"
        "AGENT_DONE:test-run-001\n"
    )
    result = ArtifactValidator().validate(task, relay=relay, sentinel_observed=True)

    assert result.accepted is True
    assert result.recovered_from_relay is True
    assert task.output_path.exists()
    saved = json.loads(task.output_path.read_text(encoding="utf-8"))
    assert saved == {"name": "bradesco", "phases": [{"id": 1}, {"id": 2}]}
    assert result.artifact_data == saved


def test_prosa_pura_rejeitada_com_artifact_invalid(task: AgentTask) -> None:
    relay = "Eu fiz a tarefa! Aqui está minha resposta em português, sem JSON."
    result = ArtifactValidator().validate(task, relay=relay, sentinel_observed=True)

    assert result.accepted is False
    assert result.failure_reason == FailureReason.ARTIFACT_INVALID
    assert "sentinel observado" in (result.failure_detail or "").lower()
    assert not task.output_path.exists()


def test_sem_sentinel_e_sem_nada_retorna_sentinel_not_observed(task: AgentTask) -> None:
    result = ArtifactValidator().validate(task, relay="", sentinel_observed=False)

    assert result.accepted is False
    assert result.failure_reason == FailureReason.SENTINEL_NOT_OBSERVED
    assert not task.output_path.exists()


def test_arquivo_existe_mas_e_texto_livre_rejeita_com_artifact_invalid(task: AgentTask) -> None:
    task.output_path.write_text("Isto não é JSON, é só prosa solta.", encoding="utf-8")
    result = ArtifactValidator().validate(task, relay="", sentinel_observed=True)

    assert result.accepted is False
    assert result.failure_reason == FailureReason.ARTIFACT_INVALID
    assert "json" in (result.failure_detail or "").lower()


# Testes adicionais cobrindo o extrator de bloco JSON e edge cases:


def test_relay_com_json_em_string_nao_confunde_chaves(task: AgentTask) -> None:
    """`{` dentro de string JSON não conta como abertura de bloco."""
    relay = '{"texto": "use { e } sempre", "n": 1}'
    result = ArtifactValidator().validate(task, relay=relay, sentinel_observed=True)
    assert result.accepted is True
    assert result.artifact_data == {"texto": "use { e } sempre", "n": 1}


def test_relay_com_json_aninhado_pega_objeto_externo(task: AgentTask) -> None:
    relay = '{"a": {"b": {"c": 42}}, "ok": true}'
    result = ArtifactValidator().validate(task, relay=relay, sentinel_observed=True)
    assert result.accepted is True
    assert result.artifact_data == {"a": {"b": {"c": 42}}, "ok": True}


def test_relay_com_chave_aberta_sem_fechar_eh_rejeitado(task: AgentTask) -> None:
    relay = "preâmbulo { que nunca fecha"
    result = ArtifactValidator().validate(task, relay=relay, sentinel_observed=True)
    assert result.accepted is False
    assert result.failure_reason == FailureReason.ARTIFACT_INVALID


def test_arquivo_com_json_array_no_objeto_eh_rejeitado(task: AgentTask) -> None:
    """Spec exige objeto raiz; array no nível raiz é rejeitado."""
    task.output_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    result = ArtifactValidator().validate(task, relay="", sentinel_observed=True)
    assert result.accepted is False
    assert result.failure_reason == FailureReason.ARTIFACT_INVALID


def test_relay_vazio_com_sentinel_eh_rejeitado(task: AgentTask) -> None:
    """Sentinel sem artefato e sem JSON no relay é rejeição com ARTIFACT_INVALID."""
    result = ArtifactValidator().validate(task, relay="AGENT_DONE:test-run-001", sentinel_observed=True)
    assert result.accepted is False
    assert result.failure_reason == FailureReason.ARTIFACT_INVALID


def test_recover_cria_diretorio_pai_se_necessario(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "deeper" / "out.json"
    task_local = AgentTask(
        run_id="r1",
        prompt="x",
        output_path=nested,
        schema_hint=None,
        workspace=tmp_path,
        timeout_hard_s=10,
        heartbeat_s=5,
    )
    relay = '{"ok": 1}'
    result = ArtifactValidator().validate(task_local, relay=relay, sentinel_observed=True)
    assert result.accepted is True
    assert nested.exists()
    assert json.loads(nested.read_text(encoding="utf-8")) == {"ok": 1}
