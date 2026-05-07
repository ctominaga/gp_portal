/**
 * Testes do comportamento da tela de revisão de baseline:
 * - source_excerpt EXPANDED por padrão (F3.5.1)
 * - Modal de ativação aparece, exige confirmação (F3.5.2)
 * - Sub-cabeçalho de auditoria com engine/route/confidence (F3.5.7)
 *
 * Usa msw via fetch interception simples (mock global de api).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Baseline } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "p1", bid: "b1" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: apiMock,
  asApiError: (e: { message: string }) => ({ message: e?.message ?? "x", status: 0 }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import BaselineReviewPage from "@/app/projetos/[id]/baseline/[bid]/page";

const fakeBaseline: Baseline = {
  id: "b1",
  project_id: "p1",
  proposal_id: "prop1",
  status: "draft",
  activated_at: null,
  activated_by_id: null,
  payload: {
    summary: "resumo",
    phases: [
      { phase_id: "fase-1", name: "F1", deliverable_count: 1 },
      { phase_id: "fase-2", name: "F2", deliverable_count: 1 },
    ],
    audit: {
      source_proposal_filename: "bradesco.pdf",
      source_proposal_version: 1,
      extracted_at: "2026-05-07T10:00:00Z",
      engine: "stub",
      route: "stub",
      confidence_score: 0.62,
    },
  },
  created_at: "2026-05-07T10:00:00Z",
  deliverables: [
    {
      id: "d1",
      code: "d-001",
      title: "Migração rotina A",
      description: null,
      phase: "fase-1",
      category: null,
      complexity: "low",
      source_excerpt: "TRECHO LITERAL DA PROPOSTA OBSERVÁVEL.",
      due_date: null,
      order_index: 0,
    },
    {
      id: "d2",
      code: "d-002",
      title: "Migração rotina B",
      description: null,
      phase: "fase-2",
      category: null,
      complexity: "high",
      source_excerpt: "OUTRO TRECHO LITERAL.",
      due_date: null,
      order_index: 1,
    },
  ],
};

describe("BaselineReviewPage", () => {
  it("renderiza source_excerpt EXPANDED por padrão (F3.5.1)", async () => {
    apiMock.get.mockResolvedValue({ data: fakeBaseline });
    render(<BaselineReviewPage />);

    // Os dois trechos aparecem visíveis (não dentro de <details> fechado)
    await waitFor(() =>
      expect(screen.getByText(/TRECHO LITERAL DA PROPOSTA/)).toBeTruthy(),
    );
    expect(screen.getByText(/OUTRO TRECHO LITERAL/)).toBeTruthy();

    // E botão "colapsar" (não "expandir") aparece — significa estado inicial = expandido
    const colapsar = screen.getAllByRole("button", { name: /colapsar/i });
    expect(colapsar.length).toBe(2);
  });

  it("ao clicar 'colapsar' o trecho some; ao clicar 'expandir' volta", async () => {
    apiMock.get.mockResolvedValue({ data: fakeBaseline });
    render(<BaselineReviewPage />);
    await waitFor(() =>
      expect(screen.getByText(/TRECHO LITERAL DA PROPOSTA/)).toBeTruthy(),
    );

    const colapsarButtons = screen.getAllByRole("button", { name: /colapsar/i });
    fireEvent.click(colapsarButtons[0]);

    expect(screen.queryByText(/TRECHO LITERAL DA PROPOSTA/)).toBeNull();

    const expandirButton = screen.getByRole("button", { name: /expandir/i });
    fireEvent.click(expandirButton);
    expect(screen.getByText(/TRECHO LITERAL DA PROPOSTA/)).toBeTruthy();
  });

  it("modal de ativação mostra contagem correta e botão 'Sim, ativar baseline' (F3.5.2)", async () => {
    apiMock.get.mockResolvedValue({ data: fakeBaseline });
    apiMock.post.mockResolvedValue({ data: { ...fakeBaseline, status: "active" } });
    render(<BaselineReviewPage />);
    await waitFor(() =>
      expect(screen.getByText(/TRECHO LITERAL DA PROPOSTA/)).toBeTruthy(),
    );

    const ativar = screen.getByRole("button", { name: /^Ativar baseline$/i });
    fireEvent.click(ativar);

    // Modal renderiza
    await waitFor(() =>
      expect(screen.getByText(/Ativar baseline\?/)).toBeTruthy(),
    );
    // Texto exato pedido pelo PO
    expect(screen.getByText(/2 entregáveis em 2 fases/)).toBeTruthy();
    expect(screen.getByText(/contrato deste projeto/)).toBeTruthy();
    expect(screen.getByText(/proposta v2/i)).toBeTruthy();
    expect(screen.getByText(/Esta ação não pode ser desfeita/)).toBeTruthy();

    const confirm = screen.getByRole("button", { name: /Sim, ativar baseline/i });
    expect(confirm).toBeTruthy();

    // Cancelar não chama post
    const cancelar = screen.getByRole("button", { name: /Cancelar/i });
    fireEvent.click(cancelar);
    expect(apiMock.post).not.toHaveBeenCalled();
  });

  it("modal de ativação confirma chama POST /baselines/{id}/activate", async () => {
    apiMock.get.mockResolvedValue({ data: fakeBaseline });
    apiMock.post.mockResolvedValue({ data: fakeBaseline });
    render(<BaselineReviewPage />);
    await waitFor(() =>
      expect(screen.getByText(/TRECHO LITERAL DA PROPOSTA/)).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: /^Ativar baseline$/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Sim, ativar baseline/i })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Sim, ativar baseline/i }));
    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith("/baselines/b1/activate"),
    );
  });

  it("sub-cabeçalho de auditoria mostra engine/rota/confiança (F3.5.7)", async () => {
    apiMock.get.mockResolvedValue({ data: fakeBaseline });
    render(<BaselineReviewPage />);
    await waitFor(() =>
      expect(screen.getByTestId("baseline-audit-header")).toBeTruthy(),
    );
    const header = screen.getByTestId("baseline-audit-header");
    expect(header.textContent).toMatch(/bradesco\.pdf/);
    expect(header.textContent).toMatch(/v1/);
    expect(header.textContent).toMatch(/stub\/stub/);
    expect(header.textContent).toMatch(/62%/);
  });

  it("contador no header e no resumo bate com deliverables.length (F3.5.8)", async () => {
    apiMock.get.mockResolvedValue({ data: fakeBaseline });
    render(<BaselineReviewPage />);
    await waitFor(() =>
      expect(screen.getByText(/2 entregáveis em 2 fases/)).toBeTruthy(),
    );
  });
});
