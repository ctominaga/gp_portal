import type { RAGStatus } from "@/lib/types";

export type Dimension = "prazo" | "escopo" | "qualidade";

export interface RagDraft {
  rag_prazo: RAGStatus | null;
  rag_escopo: RAGStatus | null;
  rag_qualidade: RAGStatus | null;
  rag_prazo_justificativa: string;
  rag_escopo_justificativa: string;
  rag_qualidade_justificativa: string;
}

export interface RagValidation {
  ok: boolean;
  missingDimensions: Dimension[];
  missingJustifications: Dimension[];
  /** rag_status agregado (worst-of-3); null se faltar dimensão */
  aggregate: RAGStatus | null;
}

const RANK: Record<RAGStatus, number> = { G: 0, A: 1, R: 2 };
const ORDER: RAGStatus[] = ["G", "A", "R"];

export function aggregateRag(
  prazo: RAGStatus | null,
  escopo: RAGStatus | null,
  qualidade: RAGStatus | null,
): RAGStatus | null {
  if (!prazo || !escopo || !qualidade) return null;
  const dims = [prazo, escopo, qualidade];
  let worst = dims[0];
  for (const d of dims) if (RANK[d] > RANK[worst]) worst = d;
  return worst;
}

/** Worst encountered nas dimensões preenchidas (mesmo se faltarem). */
export function worstFilled(
  prazo: RAGStatus | null,
  escopo: RAGStatus | null,
  qualidade: RAGStatus | null,
): RAGStatus | null {
  let worst: RAGStatus | null = null;
  for (const d of [prazo, escopo, qualidade]) {
    if (!d) continue;
    if (worst === null || RANK[d] > RANK[worst]) worst = d;
  }
  return worst;
}

/** Validação completa para botão "Submeter". */
export function validateRag(d: RagDraft): RagValidation {
  const missingDimensions: Dimension[] = [];
  if (d.rag_prazo === null) missingDimensions.push("prazo");
  if (d.rag_escopo === null) missingDimensions.push("escopo");
  if (d.rag_qualidade === null) missingDimensions.push("qualidade");

  const missingJustifications: Dimension[] = [];
  const checks: Array<[Dimension, RAGStatus | null, string]> = [
    ["prazo", d.rag_prazo, d.rag_prazo_justificativa],
    ["escopo", d.rag_escopo, d.rag_escopo_justificativa],
    ["qualidade", d.rag_qualidade, d.rag_qualidade_justificativa],
  ];
  for (const [name, val, just] of checks) {
    if ((val === "A" || val === "R") && (!just || just.trim().length === 0)) {
      missingJustifications.push(name);
    }
  }

  return {
    ok: missingDimensions.length === 0 && missingJustifications.length === 0,
    missingDimensions,
    missingJustifications,
    aggregate: aggregateRag(d.rag_prazo, d.rag_escopo, d.rag_qualidade),
  };
}

export const DIMENSION_LABELS: Record<Dimension, string> = {
  prazo: "Prazo",
  escopo: "Escopo",
  qualidade: "Qualidade",
};

export const RAG_OPTIONS = ORDER;
