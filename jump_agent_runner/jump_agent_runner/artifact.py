"""ArtifactValidator — decide se uma tentativa produziu resultado aceitável.

Spec: 02_jump_agent_runner_spec.md, seção 8.

Regras em ordem:
1. Se output_path existe e contém JSON válido → ACEITO. Schema_hint, se presente,
   é validado de forma leniente (warning, não erro).
2. Se output_path NÃO existe MAS o relay/stdout contém um bloco JSON válido completo
   → copia para output_path e ACEITA com recovered_from_relay=True.
3. Caso contrário → REJEITA. Stdout em prosa, markdown, ou apenas sentinel sem
   arquivo, é rejeição explícita.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .types import FailureReason, ValidationResult

if TYPE_CHECKING:
    from .types import AgentTask


class ArtifactValidator:
    """Valida o artefato de saída de uma tentativa de execução."""

    def validate(
        self,
        task: AgentTask,
        relay: str,
        sentinel_observed: bool,
    ) -> ValidationResult:
        # Regra 1 — output_path existe
        if task.output_path.exists():
            try:
                raw = task.output_path.read_text(encoding="utf-8")
            except OSError as exc:
                return ValidationResult.rejected(
                    FailureReason.ARTIFACT_INVALID,
                    f"output_path não pôde ser lido: {exc}",
                )
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                return ValidationResult.rejected(
                    FailureReason.ARTIFACT_INVALID,
                    f"output_path existe mas não é JSON válido: {exc.msg} "
                    f"(linha {exc.lineno}, coluna {exc.colno})",
                )
            if not isinstance(data, dict):
                return ValidationResult.rejected(
                    FailureReason.ARTIFACT_INVALID,
                    f"output_path contém JSON mas não é um objeto: tipo {type(data).__name__}",
                )
            return ValidationResult.accepted_from(task.output_path, data)

        # Regra 2 — extrai JSON balanceado do relay
        block = self._extract_json_block(relay)
        if block is not None:
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                try:
                    task.output_path.parent.mkdir(parents=True, exist_ok=True)
                    task.output_path.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except OSError as exc:
                    return ValidationResult.rejected(
                        FailureReason.ARTIFACT_INVALID,
                        f"JSON recuperado do relay mas falha ao gravar output_path: {exc}",
                    )
                return ValidationResult.accepted_from(task.output_path, data, recovered=True)

        # Regra 3 — rejeita
        if sentinel_observed:
            return ValidationResult.rejected(
                FailureReason.ARTIFACT_INVALID,
                "sentinel observado mas nenhum JSON válido encontrado em output_path nem relay",
            )
        return ValidationResult.rejected(
            FailureReason.SENTINEL_NOT_OBSERVED,
            "nem sentinel nem artefato produzidos",
        )

    @staticmethod
    def _extract_json_block(text: str) -> str | None:
        """Procura o primeiro bloco {...} balanceado em `text`.

        Considera awareness mínima de strings JSON: chaves dentro de strings
        não contam como abertura/fechamento. Strip de fences ```json se presente.
        Retorna o bloco bruto (sem parse) ou None se não encontrar nada balanceado.
        """
        if not text:
            return None

        # Remove fences markdown comuns sem se preocupar com aninhamento
        cleaned = text.replace("```json", "").replace("```JSON", "").replace("```", "")

        depth = 0
        start: int | None = None
        in_string = False
        escaped = False

        for i, ch in enumerate(cleaned):
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        return cleaned[start : i + 1]
        return None
