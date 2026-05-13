"""Builder de prompt para o AgentTask — stub mínimo (decisão B-β do F5.6a).

Em F5.6a o prompt é um template curto hardcoded por `task_type`. O contexto do
payload (`project_id`, `proposal_id`, etc.) é deliberadamente ignorado — F5.6a
roda jobs sintéticos só para validar o pipeline `Redis → AgentRunner →
callback`.

F5.6b substitui esse builder por carregamento de prompt versionado em
`docs/prompts/<task>_v<N>.md` e enriquece com o `context` real (proposta
baixada do R2, schema canônico, etc.). Ver ADR `2026-05-13 — F5.6a` em
`docs/decisoes.md`.
"""
from __future__ import annotations

_TEMPLATES: dict[str, str] = {
    "proposal_extraction": (
        "Você é o agente leitor de propostas comerciais da Jump Label. "
        "Extraia escopo, entregas e premissas da proposta indicada no contexto, "
        "produzindo o JSON canônico conforme o schema_hint fornecido."
    ),
    "report_analysis": (
        "Você é o agente analisador de reports semanais. Avalie consistência "
        "entre RAG, progresso, riscos e pendências; produza insights "
        "estruturados no JSON conforme o schema_hint."
    ),
    "portfolio_pattern": (
        "Você é o agente de inteligência cruzada de portfólio. Analise padrões "
        "emergentes entre projetos com histórico de pelo menos 3 reports e "
        "produza insights consolidados no JSON conforme o schema_hint."
    ),
}


def build_prompt(task_type: str, context: dict | None = None) -> str:  # noqa: ARG001
    """Retorna o prompt textual do agente para o `task_type`.

    F5.6a: stub mínimo (B-β). F5.6b substituirá pelo prompt versionado real.
    """
    tpl = _TEMPLATES.get(task_type)
    if tpl is None:
        raise ValueError(f"task_type desconhecido: {task_type!r}")
    return tpl


def supported_task_types() -> list[str]:
    return sorted(_TEMPLATES.keys())
