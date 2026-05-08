/**
 * Testes da tela de aprovação PMO (F4.6):
 * - Mostra RAG por dimensão com justificativa
 * - AIInsights renderizados com banner de severidade
 * - Dialog de "Pedir revisão" exige comentário
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AIInsight, Project, Report } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useParams: () => ({ rid: "r1" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
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

const toastMock = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast: toastMock }));

import ReviewReportPage from "@/app/pmo/reports/[rid]/review/page";

const fakeReport: Report = {
  id: "r1",
  project_id: "p1",
  period_start: "2026-04-29",
  period_end: "2026-05-05",
  rag_status: "A",
  rag_prazo: "A",
  rag_escopo: "G",
  rag_qualidade: "R",
  rag_prazo_justificativa: "Sprint 4 atrasou 3 dias por dependência externa.",
  rag_escopo_justificativa: null,
  rag_qualidade_justificativa: "2 bugs críticos abertos sem solução.",
  status: "submitted",
  highlights: "Concluímos integração TFS",
  next_steps: "Iniciar testes",
  notes: null,
  health_score: 58,
  created_by_id: "gp1",
  created_at: "2026-05-05T10:00:00Z",
  submitted_at: "2026-05-05T10:00:00Z",
  approved_at: null,
  progresses: [],
  risks: [
    { description: "Bug crítico no conector", severity: "critical", owner_id: null, due_date: null, status: "open" },
  ],
  action_plans: [],
  pending_items: [
    { description: "Aprovar layout", owner_party: "client", due_date: null, status: "open" },
  ],
};

const fakeProject: Project = {
  id: "p1",
  name: "Bradesco SAS→Databricks",
  client_name: "Bradesco",
  description: null,
  gp_user_id: "gp1",
  client_user_id: "cli1",
  status: "active",
  started_at: "2026-01-10",
  ended_at: null,
  created_at: "2026-01-01",
};

const fakeInsight: AIInsight = {
  id: "i1",
  scope: "project",
  project_id: "p1",
  report_id: "r1",
  agent_run_id: null,
  payload: {
    severity: "high",
    headline: "Risco crítico aberto há mais de 14 dias",
    detail: "O risco 'Bug crítico no conector' está aberto sem mitigação registrada.",
  },
  created_at: "2026-05-05T11:00:00Z",
};

function setupGets(): void {
  apiMock.get.mockImplementation((url: string) => {
    if (url === "/reports/r1") return Promise.resolve({ data: fakeReport });
    if (url === "/projects/p1") return Promise.resolve({ data: fakeProject });
    if (url === "/reports/r1/approvals") return Promise.resolve({ data: [] });
    if (url === "/reports/r1/insights") return Promise.resolve({ data: [fakeInsight] });
    return Promise.reject(new Error("unexpected " + url));
  });
}

describe("ReviewReportPage", () => {
  it("renderiza RAG por dimensão com justificativa em itálico", async () => {
    setupGets();
    render(<ReviewReportPage />);
    await waitFor(() =>
      expect(screen.getByText(/Status por dimensão/)).toBeTruthy(),
    );
    expect(screen.getByText(/Sprint 4 atrasou/)).toBeTruthy();
    expect(screen.getByText(/2 bugs críticos abertos/)).toBeTruthy();
  });

  it("AIInsights aparecem com severity high e detalhe", async () => {
    setupGets();
    render(<ReviewReportPage />);
    await waitFor(() =>
      expect(screen.getByText(/Risco crítico aberto há mais de 14 dias/)).toBeTruthy(),
    );
    expect(screen.getByText(/'Bug crítico no conector' está aberto/)).toBeTruthy();
  });

  it("'Pedir revisão' exige comentário (validação client-side)", async () => {
    setupGets();
    render(<ReviewReportPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Pedir revisão/i })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Pedir revisão/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Sim, pedir revisão/i })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Sim, pedir revisão/i }));
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith(
        expect.stringMatching(/comentário/i),
      ),
    );
    expect(apiMock.post).not.toHaveBeenCalled();
  });
});
