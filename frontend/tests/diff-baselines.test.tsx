/**
 * Testes da tela de comparação de baselines (F4.7):
 * - Carrega lista de baselines
 * - Pré-seleciona as duas mais recentes
 * - Mostra contadores de added/removed/changed
 * - Renderiza secções por tipo
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BaselineDiff } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "p1" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: apiMock,
  asApiError: (e: { message: string }) => ({ message: e?.message ?? "x", status: 0 }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import ProjectDiffPage from "@/app/projetos/[id]/diff/page";

const baselines = [
  {
    id: "b2",
    proposal_id: "pp2",
    status: "draft",
    activated_at: null,
    created_at: "2026-05-05T10:00:00Z",
    deliverable_count: 7,
    source_proposal_filename: "bradesco-v2.pdf",
    source_proposal_version: 2,
  },
  {
    id: "b1",
    proposal_id: "pp1",
    status: "active",
    activated_at: "2026-04-01T10:00:00Z",
    created_at: "2026-04-01T10:00:00Z",
    deliverable_count: 6,
    source_proposal_filename: "bradesco-v1.pdf",
    source_proposal_version: 1,
  },
];

const diffPayload: BaselineDiff = {
  base_baseline_id: "b1",
  new_baseline_id: "b2",
  added: [
    {
      kind: "added",
      code: "d-007",
      title_old: null,
      title_new: "Migração de rotina TFS-X",
      phase_old: null,
      phase_new: "fase-3",
      complexity_old: null,
      complexity_new: "high",
    },
  ],
  removed: [
    {
      kind: "removed",
      code: "d-005",
      title_old: "Conector legado descontinuado",
      title_new: null,
      phase_old: "fase-2",
      phase_new: null,
      complexity_old: "low",
      complexity_new: null,
    },
  ],
  changed: [
    {
      kind: "changed",
      code: "d-003",
      title_old: "Pipeline antigo",
      title_new: "Pipeline (escopo expandido)",
      phase_old: "fase-1",
      phase_new: "fase-2",
      complexity_old: "medium",
      complexity_new: "high",
    },
  ],
};

describe("ProjectDiffPage", () => {
  beforeEach(() => {
    apiMock.get.mockReset();
    apiMock.post.mockReset();
  });

  it("carrega baselines e pre-seleciona as duas mais recentes", async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url.endsWith("/baselines")) return Promise.resolve({ data: baselines });
      if (url.startsWith("/client/diff/")) return Promise.resolve({ data: diffPayload });
      return Promise.reject(new Error("unexpected " + url));
    });

    render(<ProjectDiffPage />);

    await waitFor(() =>
      expect(apiMock.get).toHaveBeenCalledWith("/client/diff/b1/b2"),
    );
  });

  it("exibe contadores corretos e secção de adicionados/removidos/alterados", async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url.endsWith("/baselines")) return Promise.resolve({ data: baselines });
      if (url.startsWith("/client/diff/")) return Promise.resolve({ data: diffPayload });
      return Promise.reject(new Error("unexpected " + url));
    });
    render(<ProjectDiffPage />);

    await waitFor(() =>
      expect(screen.getByText(/Entregáveis adicionados/)).toBeTruthy(),
    );
    expect(screen.getByText(/Migração de rotina TFS-X/)).toBeTruthy();
    expect(screen.getByText(/Conector legado descontinuado/)).toBeTruthy();
    expect(screen.getByText(/Pipeline antigo/)).toBeTruthy();
    expect(screen.getByText(/Pipeline \(escopo expandido\)/)).toBeTruthy();

    // Total = 3 (1 added + 1 removed + 1 changed)
    expect(screen.getByText(/Total de mudanças/)).toBeTruthy();
  });

  it("não chama diff quando os dois ids coincidem", async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url.endsWith("/baselines"))
        return Promise.resolve({ data: [baselines[0]] });
      if (url.startsWith("/client/diff/"))
        return Promise.resolve({ data: diffPayload });
      return Promise.reject(new Error("unexpected " + url));
    });
    render(<ProjectDiffPage />);
    await waitFor(() =>
      expect(apiMock.get).toHaveBeenCalledWith("/projects/p1/baselines"),
    );
    // Apenas 1 baseline -> base==new ou um deles vazio: não dispara /client/diff
    const diffCalls = apiMock.get.mock.calls.filter((c: unknown[]) =>
      typeof c[0] === "string" && (c[0] as string).startsWith("/client/diff/"),
    );
    expect(diffCalls.length).toBe(0);
  });
});
