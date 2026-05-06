# Gold standard de propostas

Este diretório contém o conjunto de propostas reais da Jump anotado manualmente, usado para validar o agente leitor de propostas (F2+).

## Conteúdo

| Slug | Origem | Qualidade da extração | Status |
|---|---|---|---|
| `bradesco_sas_databricks` | PT 20251874 — Bradesco — Squad Migração SAS para Databricks | Bom (text layer) | **Gold standard do piloto.** 21 entregáveis em 4 fases (3 sprints + phaseout). |
| `torra_governanca` | PTC 20251973 — Torra — Squad Evolução da Governança de Dados v3 | Parcial (PDF predominantemente imagem) | Tabelas comerciais OK; entregáveis técnicos exigem OCR |
| `diretriz_estrategica` | PTC 20262113 — Governança — Diretriz Estratégica v1 (baixa resolução) | Sem text layer | Exige OCR; expected.json marca `_needs_ocr` e `_no_text_layer` |

## Arquivos

- `<slug>.txt` — texto extraído via `pypdf` (commitado, fonte de verdade nos testes que não dependem do PDF original)
- `<slug>.expected.json` — backlog anotado manualmente; é o que o agente leitor deve produzir
- `extract.py` — script que regenera os `.txt` a partir dos PDFs em `../../../../propostas/`

## Por que os PDFs originais não estão no git

Tamanhos: Bradesco ~73MB, Torra ~10MB, Diretriz ~7.7MB. Total >90MB. Limite de arquivo único do GitHub é 100MB e arquivos grandes inflam o histórico. Os PDFs ficam em `Jump-GP-portal/propostas/` (fora do monorepo) e são adicionados ao `.gitignore`.

Em CI, testes que precisam dos PDFs são marcados com `@pytest.mark.skipif("not Path(...).exists()")`. Para rodar localmente, garanta que `Jump-GP-portal/propostas/` tenha os 3 PDFs.

## Contrato do `expected.json`

Resumo dos campos obrigatórios:

```json
{
  "_meta": { "annotated_by": "...", "annotated_on": "...", "source_pdf": "..." },
  "project": { "client_name": "...", "project_name": "...", "proposal_number": "..." },
  "phases": [{ "phase_id": "...", "name": "...", "rationale": "...", "deliverable_count": <int> }],
  "deliverables": [{ "id": "...", "phase_id": "...", "title": "...", "type": "...", "category": "..." }],
  "out_of_scope": [...],
  "key_premises": [...]
}
```

O schema canônico fica em `shared/schemas/proposal_extraction.json` (definido em F1).
