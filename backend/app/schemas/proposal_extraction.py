"""Schema Pydantic para o resultado do agente leitor de propostas (spec v3.1 §6.4.1).

`ProposalExtraction` é o contrato JSON canônico que o agente produz em
`output_path`. É também a base do `schema_hint` enviado ao agente, e do
parsing pelo backend antes de criar Baseline + Deliverables.

Validações cobertas:
- Regex de `id` de entregável: `^d-\\d{3}$`
- Enums fechados para `type`, `category`, `complexity` (valores observados
  na proposta gold-standard do Bradesco + termos da spec v3.1 §6.4.1)
- Limite de `source_excerpt`: 500 caracteres (proteção contra "vomitar" trecho
  longo da proposta)
- Cross-field: cada `deliverable.phase_id` existe em `phases[*].phase_id`
- Cross-field: `phases[i].deliverable_count` bate com contagem real
- IDs de entregáveis únicos

Notas de design:
- Schema cobre tanto a v3.1 §6.4.1 (campos: id/nome/descrição/fase/tipo/
  planned_date/acceptance_criteria/dependencies/source_excerpt/status) quanto
  o vocabulário do `bradesco_sas_databricks.expected.json` (category,
  complexity, type=code_migration|documentation|knowledge_transfer|
  stabilization). Campos da spec ficam opcionais; o agente preenche o que
  conseguir extrair com confiança.
- Não confundir com `app.models.domain.Deliverable` (entidade persistida).
  ProposalExtraction é DTO de boundary entre agente e backend.
"""
from __future__ import annotations

import enum
import re
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

# Regex e limites como constantes módulo-level — facilita import por testes
DELIVERABLE_ID_PATTERN = r"^d-\d{3}$"
PHASE_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,49}$"
SOURCE_EXCERPT_MAX = 500


class DeliverableType(str, enum.Enum):
    """Tipos de entregável. Valores observados no expected.json do Bradesco
    + tipos da spec v3.1 §6.4.1 (Documento/Software/Serviço/Treinamento)."""

    # Vocabulário Bradesco (piloto)
    CODE_MIGRATION = "code_migration"
    DOCUMENTATION = "documentation"
    KNOWLEDGE_TRANSFER = "knowledge_transfer"
    STABILIZATION = "stabilization"
    # Vocabulário da spec v3.1 §6.4.1
    DOCUMENT = "document"
    SOFTWARE = "software"
    SERVICE = "service"
    TRAINING = "training"


class DeliverableCategory(str, enum.Enum):
    """Eixos transversais que classificam o entregável (observados no Bradesco)."""

    TECHNICAL = "tecnico"
    TECHNICAL_REGULATORY = "tecnico-regulatorio"
    TRANSVERSAL = "transversal"


class DeliverableComplexity(str, enum.Enum):
    """Faixa de complexidade — termos PT-BR observados no expected.json."""

    LOW = "baixa"
    LOW_MEDIUM = "baixa-media"
    MEDIUM_HIGH = "media-alta"
    HIGH = "alta"


class ExtractedPhase(BaseModel):
    phase_id: Annotated[str, Field(pattern=PHASE_ID_PATTERN, max_length=50)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    rationale: Annotated[str | None, Field(max_length=2000)] = None
    deliverable_count: Annotated[int, Field(ge=0, le=500)]


class ExtractedDeliverable(BaseModel):
    id: Annotated[str, Field(pattern=DELIVERABLE_ID_PATTERN)]
    phase_id: Annotated[str, Field(pattern=PHASE_ID_PATTERN, max_length=50)]
    title: Annotated[str, Field(min_length=1, max_length=300)]
    type: DeliverableType
    category: DeliverableCategory | None = None
    complexity: DeliverableComplexity | None = None
    # Campos da spec v3.1 §6.4.1 — opcionais (o agente preenche o que conseguir)
    description: Annotated[str | None, Field(max_length=2000)] = None
    planned_date: date | None = None
    acceptance_criteria: Annotated[str | None, Field(max_length=2000)] = None
    dependencies: list[str] = Field(default_factory=list)
    source_excerpt: Annotated[str | None, Field(max_length=SOURCE_EXCERPT_MAX)] = None


class ExtractedProject(BaseModel):
    client_name: Annotated[str, Field(min_length=1, max_length=200)]
    project_name: Annotated[str, Field(min_length=1, max_length=300)]
    proposal_number: str | None = None
    domain: str | None = None
    scenario_recommended_by_jump: str | None = None
    team_composition: str | None = None
    estimated_capacity_per_sprint_hours: int | None = None
    estimated_total_capacity_hours: int | None = None
    duration_sprints: int | None = None
    sprint_length_weeks: int | None = None
    expected_acceleration_pct: str | None = None


class ProposalExtraction(BaseModel):
    """Resultado canônico do agente leitor (spec v3.1 §6.4.1).

    Cross-field validators garantem coerência interna do extração:
    referências de phase válidas, contagem por fase coerente, ids únicos.
    """

    project: ExtractedProject
    phases: Annotated[list[ExtractedPhase], Field(min_length=1)]
    deliverables: Annotated[list[ExtractedDeliverable], Field(min_length=1)]
    out_of_scope: list[str] = Field(default_factory=list)
    key_premises: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_phase_refs(self) -> "ProposalExtraction":
        known = {p.phase_id for p in self.phases}
        for d in self.deliverables:
            if d.phase_id not in known:
                raise ValueError(
                    f"deliverable {d.id} referencia phase_id={d.phase_id!r} "
                    f"que não existe em phases (conhecidas: {sorted(known)})"
                )
        return self

    @model_validator(mode="after")
    def _check_deliverable_count_per_phase(self) -> "ProposalExtraction":
        actual: dict[str, int] = {p.phase_id: 0 for p in self.phases}
        for d in self.deliverables:
            actual[d.phase_id] = actual.get(d.phase_id, 0) + 1
        for p in self.phases:
            if p.deliverable_count != actual[p.phase_id]:
                raise ValueError(
                    f"phase {p.phase_id!r} declara deliverable_count="
                    f"{p.deliverable_count} mas tem {actual[p.phase_id]} "
                    f"deliverables reais"
                )
        return self

    @model_validator(mode="after")
    def _check_ids_unique(self) -> "ProposalExtraction":
        ids = [d.id for d in self.deliverables]
        if len(ids) != len(set(ids)):
            dups = sorted({x for x in ids if ids.count(x) > 1})
            raise ValueError(f"deliverable ids duplicados: {dups}")
        return self


__all__ = [
    "DELIVERABLE_ID_PATTERN",
    "PHASE_ID_PATTERN",
    "SOURCE_EXCERPT_MAX",
    "DeliverableType",
    "DeliverableCategory",
    "DeliverableComplexity",
    "ExtractedPhase",
    "ExtractedDeliverable",
    "ExtractedProject",
    "ProposalExtraction",
]
