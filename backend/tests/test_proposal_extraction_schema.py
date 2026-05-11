"""Testes do schema ProposalExtraction (fonte: prompt `proposal_reader_v1.md`).

Cobre:
- Acid test: o `bradesco_sas_databricks.expected.json` (ground truth anotado
  manualmente) valida limpo após injetar confidence_score=100 (anotador humano
  não preenche esse campo, mas o schema canônico exige — ver nota no acid test).
- Regex de id: aceita d-NNN, rejeita formato livre.
- Cross-field: phase_id desconhecido falha.
- Cross-field: deliverable_count que não bate falha.
- IDs duplicados falham.
- source_excerpt acima de 500 chars falha.
- Enums alinhados ao prompt v1:
  * type: code_migration/documentation/knowledge_transfer/stabilization/
    deliverable_software/assessment/model/infrastructure/other
  * category: tecnico/tecnico-regulatorio/negocio/transversal/governanca
  * complexity: baixa/baixa-media/media/media-alta/alta
- Enums antigos da v3.1 (document/software/service/training) rejeitados.
- confidence_score < 80 sem confidence_notes falha; com notes passa;
  score ≥ 80 sem notes passa.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.proposal_extraction import (
    SOURCE_EXCERPT_MAX,
    DeliverableCategory,
    DeliverableComplexity,
    DeliverableType,
    ExtractedDeliverable,
    ProposalExtraction,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "proposals"
    / "bradesco_sas_databricks.expected.json"
)


def _bradesco_payload() -> dict:
    """Carrega expected.json, remove `_meta` e injeta confidence_score.

    O expected.json foi anotado manualmente por Christopher 2026-05-06 — anterior
    à definição de confidence_score no prompt v1. Anotador humano não preenche
    esse campo (é auto-avaliação do agente). Injetamos 100 + nota para que o
    ground truth valide contra o schema canônico.
    """
    with FIXTURE.open(encoding="utf-8") as f:
        d = json.load(f)
    d.pop("_meta", None)
    d.setdefault("confidence_score", 100)
    d.setdefault(
        "confidence_notes",
        ["Anotado manualmente — ground truth do piloto Bradesco"],
    )
    return d


def _minimal_valid_payload(**overrides: object) -> dict:
    """Payload mínimo que valida — útil pra testar uma variação isolada."""
    base = {
        "project": {"client_name": "X", "project_name": "Y"},
        "phases": [
            {"phase_id": "sprint-1", "name": "S1", "deliverable_count": 1}
        ],
        "deliverables": [
            {
                "id": "d-001",
                "phase_id": "sprint-1",
                "title": "t",
                "type": "code_migration",
                "category": "tecnico",
            }
        ],
        "confidence_score": 95,
        "confidence_notes": [],
    }
    base.update(overrides)
    return base


def test_schema_valida_expected_bradesco_acid_test() -> None:
    """Se o schema rejeita o ground truth (com confidence injetado),
    o schema está errado. Teste mais importante do arquivo."""
    payload = _bradesco_payload()
    obj = ProposalExtraction.model_validate(payload)
    assert obj.project.client_name == "Bradesco"
    assert len(obj.deliverables) == 21
    assert len(obj.phases) == 4
    assert obj.confidence_score == 100


def test_id_regex_aceita_d_NNN_e_rejeita_formato_livre() -> None:
    base = {
        "phase_id": "sprint-1",
        "title": "x",
        "type": "code_migration",
    }
    ExtractedDeliverable.model_validate({**base, "id": "d-001"})
    ExtractedDeliverable.model_validate({**base, "id": "d-999"})
    for bad in ["d-1", "d-0001", "deliv-001", "D-001", "001", ""]:
        with pytest.raises(ValidationError):
            ExtractedDeliverable.model_validate({**base, "id": bad})


def test_phase_ref_desconhecido_falha() -> None:
    payload = _minimal_valid_payload(
        deliverables=[
            {
                "id": "d-001",
                "phase_id": "sprint-9",  # não existe em phases
                "title": "t",
                "type": "code_migration",
                "category": "tecnico",
            }
        ],
    )
    with pytest.raises(ValidationError) as exc:
        ProposalExtraction.model_validate(payload)
    assert "sprint-9" in str(exc.value)


def test_deliverable_count_inconsistente_falha() -> None:
    payload = _minimal_valid_payload(
        phases=[
            {"phase_id": "sprint-1", "name": "S1", "deliverable_count": 3}
        ],
    )
    with pytest.raises(ValidationError) as exc:
        ProposalExtraction.model_validate(payload)
    assert "deliverable_count" in str(exc.value)


def test_deliverable_ids_duplicados_falham() -> None:
    payload = _minimal_valid_payload(
        phases=[
            {"phase_id": "sprint-1", "name": "S1", "deliverable_count": 2}
        ],
        deliverables=[
            {"id": "d-001", "phase_id": "sprint-1", "title": "a",
             "type": "code_migration", "category": "tecnico"},
            {"id": "d-001", "phase_id": "sprint-1", "title": "b",
             "type": "code_migration", "category": "tecnico"},
        ],
    )
    with pytest.raises(ValidationError) as exc:
        ProposalExtraction.model_validate(payload)
    assert "duplicad" in str(exc.value).lower()


def test_source_excerpt_acima_de_500_chars_falha() -> None:
    base = {
        "id": "d-001",
        "phase_id": "sprint-1",
        "title": "t",
        "type": "code_migration",
    }
    ExtractedDeliverable.model_validate(
        {**base, "source_excerpt": "x" * SOURCE_EXCERPT_MAX}
    )
    with pytest.raises(ValidationError):
        ExtractedDeliverable.model_validate(
            {**base, "source_excerpt": "x" * (SOURCE_EXCERPT_MAX + 1)}
        )


# ---------- Enums alinhados ao prompt v1 ----------


def test_type_enum_aceita_todos_os_9_valores_do_prompt_v1() -> None:
    """Prompt §3 lista 9 tipos. Cada um deve validar."""
    for t in (
        "code_migration",
        "documentation",
        "knowledge_transfer",
        "stabilization",
        "deliverable_software",
        "assessment",
        "model",
        "infrastructure",
        "other",
    ):
        ExtractedDeliverable.model_validate(
            {
                "id": "d-001",
                "phase_id": "sprint-1",
                "title": "t",
                "type": t,
            }
        )


def test_type_enum_rejeita_valores_antigos_da_v3_1() -> None:
    """A v3.1 §6.4.1 listava document/software/service/training. Após o
    alinhamento com o prompt v1, esses valores não são mais aceitos."""
    for old in ("document", "software", "service", "training"):
        with pytest.raises(ValidationError):
            ExtractedDeliverable.model_validate(
                {
                    "id": "d-001",
                    "phase_id": "sprint-1",
                    "title": "t",
                    "type": old,
                }
            )


def test_category_enum_aceita_todos_os_5_valores_do_prompt_v1() -> None:
    """Prompt §3 lista 5 categorias. Cada uma deve validar."""
    for c in (
        "tecnico",
        "tecnico-regulatorio",
        "negocio",
        "transversal",
        "governanca",
    ):
        ExtractedDeliverable.model_validate(
            {
                "id": "d-001",
                "phase_id": "sprint-1",
                "title": "t",
                "type": "code_migration",
                "category": c,
            }
        )


def test_complexity_enum_aceita_todos_os_5_niveis_inclusive_media() -> None:
    """Prompt §3 lista 5 níveis incluindo 'media' que faltava no schema antigo."""
    for c in ("baixa", "baixa-media", "media", "media-alta", "alta"):
        ExtractedDeliverable.model_validate(
            {
                "id": "d-001",
                "phase_id": "sprint-1",
                "title": "t",
                "type": "code_migration",
                "complexity": c,
            }
        )


# ---------- Confidence ----------


def test_confidence_score_baixo_sem_notes_falha() -> None:
    """Prompt §5: score < 80 sem notes é sinal de extração desatenta."""
    payload = _minimal_valid_payload(confidence_score=75, confidence_notes=[])
    with pytest.raises(ValidationError) as exc:
        ProposalExtraction.model_validate(payload)
    assert "confidence_notes" in str(exc.value)


def test_confidence_score_baixo_com_notes_passa() -> None:
    payload = _minimal_valid_payload(
        confidence_score=75,
        confidence_notes=["Fronteiras entre sprint-2 e sprint-3 ambíguas"],
    )
    obj = ProposalExtraction.model_validate(payload)
    assert obj.confidence_score == 75


def test_confidence_score_alto_sem_notes_passa() -> None:
    """Score ≥ 80 não exige notes."""
    payload = _minimal_valid_payload(confidence_score=90, confidence_notes=[])
    obj = ProposalExtraction.model_validate(payload)
    assert obj.confidence_score == 90


def test_confidence_score_fora_de_0_100_falha() -> None:
    for bad in (-1, 101, 150):
        payload = _minimal_valid_payload(confidence_score=bad)
        with pytest.raises(ValidationError):
            ProposalExtraction.model_validate(payload)


def test_confidence_score_obrigatorio() -> None:
    """Prompt §5 lista confidence_score em 'CAMPOS OBRIGATÓRIOS'."""
    payload = _minimal_valid_payload()
    del payload["confidence_score"]
    with pytest.raises(ValidationError) as exc:
        ProposalExtraction.model_validate(payload)
    assert "confidence_score" in str(exc.value)


def test_phases_e_deliverables_nao_vazios() -> None:
    """min_length=1 garante que extração vazia não vira Baseline órfão."""
    with pytest.raises(ValidationError):
        ProposalExtraction.model_validate(_minimal_valid_payload(phases=[]))
    with pytest.raises(ValidationError):
        ProposalExtraction.model_validate(_minimal_valid_payload(deliverables=[]))


def test_smoke_dos_enums_exportados() -> None:
    """Garante que os módulos consumidores podem importar os enums esperados."""
    assert DeliverableType.OTHER.value == "other"
    assert DeliverableCategory.BUSINESS.value == "negocio"
    assert DeliverableCategory.GOVERNANCE.value == "governanca"
    assert DeliverableComplexity.MEDIUM.value == "media"
