import type { RAGStatus, ProposalStatus, ReportStatus } from "@/lib/types";

export function ragColor(status: RAGStatus | null | undefined): "green" | "amber" | "red" | "outline" {
  switch (status) {
    case "G":
      return "green";
    case "A":
      return "amber";
    case "R":
      return "red";
    default:
      return "outline";
  }
}

export function ragLabel(status: RAGStatus | null | undefined): string {
  if (!status) return "—";
  return ({ G: "Verde", A: "Amarelo", R: "Vermelho" } as const)[status] ?? "—";
}

export function proposalStatusLabel(s: ProposalStatus): string {
  return {
    pending_extraction: "Extraindo…",
    extracted: "Extraída",
    needs_ocr: "Necessita OCR",
    superseded: "Substituída",
    extraction_failed: "Falha na extração",
  }[s];
}

export function reportStatusLabel(s: ReportStatus): string {
  return {
    draft: "Rascunho",
    submitted: "Submetido",
    pmo_approved: "Aprovado PMO",
    client_released: "Liberado",
    archived: "Arquivado",
    needs_revision: "Revisão pedida",
  }[s];
}

export function humanizeAgo(seconds: number): string {
  if (seconds < 60) return `${seconds}s atrás`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min atrás`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)}h atrás`;
  return `${Math.round(seconds / 86_400)}d atrás`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pt-BR");
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(1)} GB`;
}
