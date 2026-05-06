"""Extrai texto dos PDFs em ../../../../propostas/ e grava em fixtures.

Roda fora do pytest, via:
    py -3.10 backend/tests/fixtures/proposals/extract.py

PDFs originais não são commitados (alguns >50MB). O texto extraído sim.
"""
from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROPOSALS_SRC = ROOT.parent / "propostas"

MAPPING = {
    "PT 20251874 - Bradesco - Squad Migração SAS para Databricks.pdf": "bradesco_sas_databricks",
    "PTC 20251973 - Torra - Squad Evolução da Governança de Dados v3.pdf": "torra_governanca",
    "PTC 20262113 - Governança - Diretriz Estratégica Uso e Evolução Dados v1 (versão resolução baixa).pdf": "diretriz_estrategica",
}


def extract(pdf_path: Path, out_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            text = f"[ERRO_EXTRACAO pagina={i}: {exc}]"
        parts.append(f"\n\n----- PÁGINA {i} -----\n{text.strip()}\n")
    out_path.write_text("".join(parts), encoding="utf-8")
    return len(reader.pages)


def main() -> int:
    if not PROPOSALS_SRC.exists():
        print(f"ERRO: pasta de propostas não encontrada: {PROPOSALS_SRC}", file=sys.stderr)
        return 1
    HERE.mkdir(parents=True, exist_ok=True)
    for src_name, slug in MAPPING.items():
        src = PROPOSALS_SRC / src_name
        if not src.exists():
            print(f"AVISO: PDF ausente: {src}", file=sys.stderr)
            continue
        out = HERE / f"{slug}.txt"
        n = extract(src, out)
        print(f"{slug}: {n} paginas -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
