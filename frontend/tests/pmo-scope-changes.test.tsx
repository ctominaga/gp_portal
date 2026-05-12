/**
 * F5.2 — Rota /pmo/scope-changes (lista portfólio-wide).
 * Cobre: render com 2 projetos diferentes, vazio, filtro por status.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ScopeChange } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
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

import PmoScopeChangesPage from "@/app/pmo/scope-changes/page";

const projectA = "11111111-1111-1111-1111-111111111111";
const projectB = "22222222-2222-2222-2222-222222222222";
const baselineA2 = "aaaa1111-aaaa-1111-aaaa-111111111111";
const baselineB2 = "bbbb2222-bbbb-2222-bbbb-222222222222";

const proposedRows: ScopeChange[] = [
  {
    id: "sc-a1",
    project_id: projectA,
    description: "Adicionado: d-101 · Migrar relatório X",
    baseline_from_id: null,
    baseline_to_id: baselineA2,
    change_type: "added",
    deliverable_code: "d-101",
    status: "proposed",
    requested_at: "2026-05-09T10:00:00Z",
    decided_at: null,
    approved_by_id: null,
  },
  {
    id: "sc-a2",
    project_id: projectA,
    description: "Modificado: d-102 (complexity: media → alta)",
    baseline_from_id: null,
    baseline_to_id: baselineA2,
    change_type: "modified",
    deliverable_code: "d-102",
    status: "proposed",
    requested_at: "2026-05-10T08:00:00Z",
    decided_at: null,
    approved_by_id: null,
  },
  {
    id: "sc-b1",
    project_id: projectB,
    description: "Removido: d-201 · Atividade descontinuada",
    baseline_from_id: null,
    baseline_to_id: baselineB2,
    change_type: "removed",
    deliverable_code: "d-201",
    status: "proposed",
    requested_at: "2026-05-11T09:00:00Z",
    decided_at: null,
    approved_by_id: null,
  },
];

const projects = [
  {
    id: projectA, name: "Bradesco SAS", client_name: "Bradesco",
    description: null, gp_user_id: "u1", client_user_id: null,
    status: "active", started_at: null, ended_at: null, created_at: "",
  },
  {
    id: projectB, name: "Itaú Datalake", client_name: "Itaú",
    description: null, gp_user_id: "u2", client_user_id: null,
    status: "active", started_at: null, ended_at: null, created_at: "",
  },
];

describe("PmoScopeChangesPage", () => {
  beforeEach(() => {
    apiMock.get.mockReset();
    apiMock.post.mockReset();
  });

  it("agrupa por (project, baseline_to) e mostra 2 linhas para 2 projetos diferentes", async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url.startsWith("/scope-changes")) return Promise.resolve({ data: proposedRows });
      if (url === "/projects") return Promise.resolve({ data: projects });
      return Promise.reject(new Error("unexpected " + url));
    });

    render(<PmoScopeChangesPage />);

    await waitFor(() =>
      expect(screen.getByText(/Bradesco SAS/)).toBeTruthy(),
    );
    // 2 transições — 1 por baseline_to. Bradesco tem 2 ScopeChanges
    // agrupados num único batch (mesmo baseline_to).
    expect(screen.getByTestId(`transition-row-${baselineA2}`)).toBeTruthy();
    expect(screen.getByTestId(`transition-row-${baselineB2}`)).toBeTruthy();
    // Itaú aparece com 1 item, Bradesco com 2 — pelo menos um "2 item(ns)"
    // tem que existir.
    expect(screen.getByText(/2 item\(ns\)/)).toBeTruthy();
    expect(screen.getByText(/Itaú Datalake/)).toBeTruthy();
  });

  it("renderiza estado vazio quando não há transições", async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url.startsWith("/scope-changes")) return Promise.resolve({ data: [] });
      if (url === "/projects") return Promise.resolve({ data: [] });
      return Promise.reject(new Error("unexpected " + url));
    });
    render(<PmoScopeChangesPage />);
    await waitFor(() =>
      expect(screen.getByText(/Nenhuma transição encontrada/)).toBeTruthy(),
    );
  });

  it("chama API com o status do filtro selecionado (default proposed)", async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url.startsWith("/scope-changes")) return Promise.resolve({ data: proposedRows });
      if (url === "/projects") return Promise.resolve({ data: projects });
      return Promise.reject(new Error("unexpected " + url));
    });
    render(<PmoScopeChangesPage />);
    await waitFor(() =>
      expect(apiMock.get).toHaveBeenCalledWith("/scope-changes?status=proposed"),
    );
  });
});
