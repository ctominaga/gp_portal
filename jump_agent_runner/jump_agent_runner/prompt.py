"""Envelope canônico de prompt — comum a todas as rotas (headless e broker).

Spec: 02_jump_agent_runner_spec.md, seção 7.
"""
from __future__ import annotations

from .types import AgentTask

ENVELOPE_TEMPLATE = """\
Você está executando uma tarefa em modo não-interativo. Siga estritamente as regras:

TAREFA:
{prompt}

CONTRATO DE SAÍDA — OBRIGATÓRIO:
1. Escreva o resultado final como JSON válido no arquivo:
   {output_path}
   (caminho absoluto, já existe o diretório pai)

2. O JSON deve obedecer ao schema:
   {schema}

3. Após escrever o arquivo, emita EXATAMENTE esta linha em stdout:
   AGENT_DONE:{run_id}

4. NÃO responda em prosa. NÃO use markdown. NÃO explique seu raciocínio.
   Apenas escreva o arquivo e emita o sentinel.

5. Se você não conseguir produzir resultado válido, escreva no arquivo:
   {{"status": "error", "reason": "<motivo curto>"}}
   e ainda assim emita AGENT_DONE:{run_id}

Workspace: {workspace}
{continuation_block}"""


def wrap_prompt(task: AgentTask) -> str:
    """Aplica o envelope §7 da spec ao prompt do task."""
    if task.schema_hint:
        # JSON formatado curto; o agente não precisa do schema completo se for muito grande
        import json

        schema_str = json.dumps(task.schema_hint, ensure_ascii=False, indent=2)
    else:
        schema_str = "esquema livre, mas válido"

    continuation_block = ""
    if task.continuation_hint:
        continuation_block = (
            "\nCONTINUAÇÃO DE TENTATIVA ANTERIOR:\n" + task.continuation_hint.strip() + "\n"
        )

    return ENVELOPE_TEMPLATE.format(
        prompt=task.prompt.strip(),
        output_path=str(task.output_path),
        schema=schema_str,
        run_id=task.run_id,
        workspace=str(task.workspace),
        continuation_block=continuation_block,
    )


def sentinel_for(run_id: str) -> str:
    """String exata que o agente deve emitir em stdout ao concluir."""
    return f"AGENT_DONE:{run_id}"
