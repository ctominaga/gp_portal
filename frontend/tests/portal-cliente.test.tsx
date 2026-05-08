/**
 * Testes do Portal do Cliente (F4.7):
 * - Lista pendências consolidadas no topo da página de projeto
 * - Botão "Confirmar leitura" só aparece em reports pmo_approved
 * - Confirmar chama POST /client/reports/{id}/confirm-read
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ClientProjectView } from "@/lib/types";

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

import ClientProjectPage from "@/app/portal/projetos/[id]/page";

const fakeView: ClientProjectView = {
  id: "p1",
  name: "Bradesco SAS→Databricks",
  client_name: "Bradesco",
  status: "active",
  started_at: "2026-01-10",
  latest_rag: "A",
  health_score: 56,
  open_pending_items: 2,
  open_risks_count: 3,
  reports: [
    {
      id: "r-novo",
      period_start: "2026-04-29",
      period_end: "2026-05-05",
      rag_status: "A",
      status: "pmo_approved",
      highlights: "Sprint 4 concluído",
      next_steps: "Iniciar testes de carga",
      submitted_at: "2026-05-05T12:00:00Z",
      approved_at: null,
      pending_items: [
        { description: "Aprovar layout do dashboard", due_date: "2026-05-10", owner_party: "client" },
        { description: "Revisar termo de uso", due_date: null, owner_party: "client" },
      ],
    },
    {
      id: "r-velho",
      period_start: "2026-04-22",
      period_end: "2026-04-28",
      rag_status: "G",
      status: "client_released",
      highlights: "Sprint 3 ok",
      next_steps: null,
      submitted_at: "2026-04-28T12:00:00Z",
      approved_at: "2026-04-29T08:00:00Z",
      pending_items: [],
    },
  ],
};

describe("ClientProjectPage", () => {
  it("renderiza gauge grande e badges de status agregados", async () => {
    apiMock.get.mockResolvedValue({ data: fakeView });
    render(<ClientProjectPage />);

    await waitFor(() =>
      expect(screen.getByText(/Bradesco SAS/)).toBeTruthy(),
    );
    expect(screen.getByText("56")).toBeTruthy();
    expect(screen.getByText(/Atenção/)).toBeTruthy();
    expect(screen.getByText(/1 report\(s\) aguardando sua leitura/)).toBeTruthy();
    expect(screen.getByText(/2 pendência\(s\) com você/)).toBeTruthy();
  });

  it("lista pendências consolidadas em destaque (F3.5: agregado visível)", async () => {
    apiMock.get.mockResolvedValue({ data: fakeView });
    render(<ClientProjectPage />);
    await waitFor(() =>
      expect(screen.getByText(/Pendências aguardando você/)).toBeTruthy(),
    );
    expect(screen.getByText(/Aprovar layout do dashboard/)).toBeTruthy();
    expect(screen.getByText(/Revisar termo de uso/)).toBeTruthy();
  });

  it("mostra botão 'Confirmar leitura' só no report pmo_approved", async () => {
    apiMock.get.mockResolvedValue({ data: fakeView });
    render(<ClientProjectPage />);
    await waitFor(() =>
      expect(screen.getByText(/Bradesco SAS/)).toBeTruthy(),
    );
    const buttons = screen.getAllByRole("button", { name: /Confirmar leitura/i });
    expect(buttons.length).toBe(1);
  });

  it("clicar 'Confirmar leitura' chama POST /client/reports/{id}/confirm-read", async () => {
    apiMock.get.mockResolvedValueOnce({ data: fakeView });
    apiMock.post.mockResolvedValue({ data: { ack: "ok" } });
    apiMock.get.mockResolvedValueOnce({
      data: {
        ...fakeView,
        reports: [
          { ...fakeView.reports[0], status: "client_released" },
          fakeView.reports[1],
        ],
      },
    });
    render(<ClientProjectPage />);
    await waitFor(() =>
      expect(screen.getByText(/Bradesco SAS/)).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Confirmar leitura/i }));
    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith("/client/reports/r-novo/confirm-read"),
    );
  });
});
