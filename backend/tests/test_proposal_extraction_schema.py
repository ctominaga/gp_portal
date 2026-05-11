"""Testes do schema ProposalExtraction (spec v3.1 §6.4.1).

Cobre:
- Acid test: o `bradesco_sas_databricks.expected.json` (proposta gold-standard
  anotada por Christopher) deve validar limpo — se o schema rejeitar o ground
  truth do piloto, o schema está errado, não o dado.
- Regex de id: aceita d-NNN, rejeita formato livre.
- Cross-field: phase_id desconhecido → falha.
- Cross-field: deliverable_count que não bate com contagem real → falha.
- IDs duplicados → falha.
- source_excerpt acima de 500 chars → falha.
- Enums fechados para type/category/complexity → rejeita valor não-mapeado.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.proposal_extraction import (
    SOURCE_EXCERPT_MAX,
    DeliverableType,
    ExtractedDeliverable,
    ExtractedPhase,
    ExtractedProject,
    ProposalExtraction,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "proposals"
    / "bradesco_sas_databricks.expected.json"
)


def _bradesco_payload() -> dict:
    """Carrega expected.json e remove `_meta` (não faz parte do contrato)."""
    with FIXTURE.open(encoding="utf-8") as f:
        d = json.load(f)
    d.pop("_meta", None)
    return d


def test_schema_valida_expected_bradesco_acid_test() -> None:
    """Se o schema rejeita o ground truth anotado por Christopher,
    o schema está errado. Este é o teste mais importante do arquivo."""
    payload = _bradesco_payload()
    obj = ProposalExtraction.model_validate(payload)
    assert obj.project.client_name == "Bradesco"
    assert len(obj.deliverables) == 21
    assert len(obj.phases) == 4
    # IDs vão de d-001 a d-021
    ids = [d.id for d in obj.deliverables]
    assert ids[0] == "d-001"
    assert ids[-1] == "d-021"


def test_id_regex_aceita_d_NNN_e_rejeita_formato_livre() -> None:
    base = {
        "phase_id": "sprint-1",
        "title": "x",
        "type": "code_migration",
    }
    # OK
    ExtractedDeliverable.model_validate({**base, "id": "d-001"})
    ExtractedDeliverable.model_validate({**base, "id": "d-999"})
    # Falham
    for bad in ["d-1", "d-0001", "deliv-001", "D-001", "001", ""]:
        with pytest.raises(ValidationError):
            ExtractedDeliverable.model_validate({**base, "id": bad})


def test_phase_ref_desconhecido_falha() -> None:
    payload = {
        "project": {"client_name": "X", "project_name": "Y"},
        "phases": [
            {"phase_id": "sprint-1", "name": "S1", "deliverable_count": 1}
        ],
        "deliverables": [
            {
                "id": "d-001",
                "phase_id": "sprint-9",  # não existe em phases
                "title": "t",
                "type": "code_migration",
            }
        ],
    }
    with pytest.raises(ValidationError) as exc:
        ProposalExtraction.model_validate(payload)
    assert "sprint-9" in str(exc.value)


def test_deliverable_count_inconsistente_falha() -> None:
    payload = {
        "project": {"client_name": "X", "project_name": "Y"},
        "phases": [
            {"phase_id": "sprint-1", "name": "S1", "deliverable_count": 3}  # diz 3
        ],
        "deliverables": [
            {"id": "d-001", "phase_id": "sprint-1", "title": "t",
             "type": "code_migration"},
        ],
    }
    with pytest.raises(ValidationError) as exc:
        ProposalExtraction.model_validate(payload)
    assert "deliverable_count" in str(exc.value)


def test_deliverable_ids_duplicados_falham() -> None:
    payload = {
        "project": {"client_name": "X", "project_name": "Y"},
        "phases": [
            {"phase_id": "sprint-1", "name": "S1", "deliverable_count": 2}
        ],
        "deliverables": [
            {"id": "d-001", "phase_id": "sprint-1", "title": "a",
             "type": "code_migration"},
            {"id": "d-001", "phase_id": "sprint-1", "title": "b",
             "type": "code_migration"},
        ],
    }
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
    # OK no limite
    ExtractedDeliverable.model_validate(
        {**base, "source_excerpt": "x" * SOURCE_EXCERPT_MAX}
    )
    # Falha 1 char acima
    with pytest.raises(ValidationError):
        ExtractedDeliverable.model_validate(
            {**base, "source_excerpt": "x" * (SOURCE_EXCERPT_MAX + 1)}
        )


def test_type_enum_fechado_rejeita_valor_nao_mapeado() -> None:
    with pytest.raises(ValidationError):
        ExtractedDeliverable.model_validate(
            {
                "id": "d-001",
                "phase_id": "sprint-1",
                "title": "t",
                "type": "tipo_inventado",
            }
        )


def test_complexity_enum_fechado_aceita_termos_ptbr() -> None:
    # Valores PT-BR observados no expected.json
    for c in ("baixa", "baixa-media", "media-alta", "alta"):
        ExtractedDeliverable.model_validate(
            {
                "id": "d-001",
                "phase_id": "sprint-1",
                "title": "t",
                "type": "code_migration",
                "complexity": c,
            }
        )
    with pytest.raises(ValidationError):
        ExtractedDeliverable.model_validate(
            {
                "id": "d-001",
                "phase_id": "sprint-1",
                "title": "t",
                "type": "code_migration",
                "complexity": "low",  # inglês não está no enum
            }
        )


def test_phases_e_deliverables_nao_vazios() -> None:
    """min_length=1 garante que extração vazia não vira Baseline órfão."""
    with pytest.raises(ValidationError):
        ProposalExtraction.model_validate(
            {
                "project": {"client_name": "X", "project_name": "Y"},
                "phases": [],
                "deliverables": [
                    {"id": "d-001", "phase_id": "sprint-1", "title": "t",
                     "type": "code_migration"}
                ],
            }
        )
    with pytest.raises(ValidationError):
        ProposalExtraction.model_validate(
            {
                "project": {"client_name": "X", "project_name": "Y"},
                "phases": [
                    {"phase_id": "sprint-1", "name": "S1", "deliverable_count": 0}
                ],
                "deliverables": [],
            }
        )
