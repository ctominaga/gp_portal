/**
 * F5.4 — UI /projetos/[id]/reports/novo com escolha de modo
 * (pré-popular vs do zero).
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "p-1" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const apiMock = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: apiMock,
  asApiError: (e: { response?: { status?: number; data?: { detail?: string } }; message?: string }) => ({
    message: e?.response?.data?.detail ?? e?.message ?? "x",
    status: e?.response?.status ?? 0,
  }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { id: "u-gp", name: "GP", email: "gp@x.com", role: "GP", created_at: "" },
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

import NewReportPage from "@/app/projetos/[id]/reports/novo/page";

describe("NewReportPage — F5.4 escolha de modo", () => {
  beforeEach(() => {
    apiMock.get.mockReset();
    apiMock.post.mockReset();
  });

  it("pré-marca 'pré-popular' quando há report anterior", async () => {
    apiMock.get.mockResolvedValue({
      data: [{ id: "old-1", period_start: "2026-04-01", period_end: "2026-04-15" }],
    });
    render(<NewReportPage />);
    // Estado inicial é "scratch"; useEffect resolve a Promise do GET e
    // muda para "prepopulate" — aguardar a mudança refletir no DOM.
    await waitFor(() => {
      const prepop = screen.getByTestId("radio-prepopulate") as HTMLInputElement;
      expect(prepop.checked).toBe(true);
    });
    const prepop = screen.getByTestId("radio-prepopulate") as HTMLInputElement;
    const scratch = screen.getByTestId("radio-scratch") as HTMLInputElement;
    expect(scratch.checked).toBe(false);
    expect(prepop.disabled).toBe(false);
  });

  it("pré-marca 'do zero' e desabilita 'pré-popular' quando não há report anterior", async () => {
    apiMock.get.mockResolvedValue({ data: [] });
    render(<NewReportPage />);
    await waitFor(() => screen.getByTestId("radio-scratch"));
    const prepop = screen.getByTestId("radio-prepopulate") as HTMLInputElement;
    const scratch = screen.getByTestId("radio-scratch") as HTMLInputElement;
    expect(prepop.disabled).toBe(true);
    expect(scratch.checked).toBe(true);
    expect(screen.getByTestId("prepopulate-disabled-hint")).toBeTruthy();
  });

  it("modo 'pré-popular' chama POST /projects/{id}/reports/prepopulate", async () => {
    apiMock.get.mockResolvedValue({ data: [{ id: "old-1" }] });
    apiMock.post.mockResolvedValue({ data: { id: "new-1" } });
    render(<NewReportPage />);
    await waitFor(() => screen.getByTestId("radio-prepopulate"));

    act(() => {
      fireEvent.change(screen.getByLabelText(/Início/), {
        target: { value: "2026-05-01" },
      });
      fireEvent.change(screen.getByLabelText(/Fim/), {
        target: { value: "2026-05-15" },
      });
    });
    act(() => {
      fireEvent.submit(screen.getByTestId("btn-submit").closest("form")!);
    });

    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith(
        "/projects/p-1/reports/prepopulate",
        expect.objectContaining({
          period_start: "2026-05-01",
          period_end: "2026-05-15",
        }),
      ),
    );
  });

  it("modo 'do zero' chama POST /reports com project_id no body", async () => {
    apiMock.get.mockResolvedValue({ data: [] });
    apiMock.post.mockResolvedValue({ data: { id: "new-2" } });
    render(<NewReportPage />);
    await waitFor(() => screen.getByTestId("radio-scratch"));

    act(() => {
      fireEvent.change(screen.getByLabelText(/Início/), {
        target: { value: "2026-05-01" },
      });
      fireEvent.change(screen.getByLabelText(/Fim/), {
        target: { value: "2026-05-15" },
      });
    });
    act(() => {
      fireEvent.submit(screen.getByTestId("btn-submit").closest("form")!);
    });

    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith(
        "/reports",
        expect.objectContaining({
          project_id: "p-1",
          period_start: "2026-05-01",
          period_end: "2026-05-15",
        }),
      ),
    );
  });

  it("409 do prepopulate (período duplicado) abre modal com link para report existente", async () => {
    apiMock.get.mockResolvedValue({
      data: [{ id: "old-1", period_start: "2026-04-01", period_end: "2026-04-15" }],
    });
    const existingId = "11111111-2222-3333-4444-555555555555";
    apiMock.post.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 409,
        data: {
          detail:
            `Já existe report no período 2026-05-01–2026-05-15. ` +
            `Acesse-o em /reports/${existingId}.`,
        },
      },
      message: "Request failed with status code 409",
    });
    render(<NewReportPage />);
    await waitFor(() => {
      const prepop = screen.getByTestId("radio-prepopulate") as HTMLInputElement;
      expect(prepop.checked).toBe(true);
    });

    act(() => {
      fireEvent.change(screen.getByLabelText(/Início/), {
        target: { value: "2026-05-01" },
      });
      fireEvent.change(screen.getByLabelText(/Fim/), {
        target: { value: "2026-05-15" },
      });
    });
    act(() => {
      fireEvent.submit(screen.getByTestId("btn-submit").closest("form")!);
    });

    // Modal abre com link extraído da mensagem
    await waitFor(() => screen.getByText(/Report já existe nesse período/));
    // Button asChild faz o data-testid recair no Link (anchor) diretamente.
    const link = screen.getByTestId("btn-open-existing-report");
    expect(link.getAttribute("href")).toBe(
      `/projetos/p-1/reports/${existingId}/edit`,
    );
  });
});
