/**
 * F5.7 — Tela /admin/data-requests (RAT LGPD, role PMO).
 * Cobre: render + filtros + criação manual + fulfill confirm.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DataProcessingRecord, DataProcessingRecordList } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const apiMock = vi.hoisted(() => ({
  list: vi.fn(),
  createManual: vi.fn(),
  fulfill: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiAdminDataRequests: apiMock,
  asApiError: (e: { message?: string }) => ({
    message: e?.message ?? "x",
    status: 0,
  }),
}));

const toastMock = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast: toastMock }));

import AdminDataRequestsPage from "@/app/admin/data-requests/page";

const RECORDS: DataProcessingRecord[] = [
  {
    id: "rec-1",
    subject_user_id: null,
    subject_external_email: "ext@cliente.com",
    request_type: "deletion",
    status: "pending",
    requested_at: "2026-05-15T10:00:00Z",
    fulfilled_at: null,
    handled_by_id: null,
    notes: "Recebido por e-mail.",
  },
  {
    id: "rec-2",
    subject_user_id: "11111111-2222-3333-4444-555555555555",
    subject_external_email: null,
    request_type: "export",
    status: "fulfilled",
    requested_at: "2026-05-14T09:00:00Z",
    fulfilled_at: "2026-05-14T09:01:00Z",
    handled_by_id: "pmo-1",
    notes: null,
  },
];

function pageOf(items: DataProcessingRecord[]): DataProcessingRecordList {
  return { items, total: items.length, page: 1, page_size: 50 };
}

describe("AdminDataRequestsPage", () => {
  beforeEach(() => {
    apiMock.list.mockReset();
    apiMock.createManual.mockReset();
    apiMock.fulfill.mockReset();
    toastMock.success.mockReset();
    toastMock.error.mockReset();
  });

  it("renderiza a tabela com os pedidos retornados e chama list com status=pending por default", async () => {
    apiMock.list.mockResolvedValue(pageOf(RECORDS));
    render(<AdminDataRequestsPage />);

    await waitFor(() =>
      expect(screen.getByText("ext@cliente.com")).toBeTruthy(),
    );
    expect(screen.getByText(/Interno · 11111111/)).toBeTruthy();
    expect(apiMock.list).toHaveBeenCalledWith(
      expect.objectContaining({ status: "pending" }),
    );

    // Botão "Atender" do FULFILLED está desabilitado (idempotência visual).
    const fulfillBtn2 = screen.getByTestId(
      "btn-fulfill-rec-2",
    ) as HTMLButtonElement;
    expect(fulfillBtn2.disabled).toBe(true);
    const fulfillBtn1 = screen.getByTestId(
      "btn-fulfill-rec-1",
    ) as HTMLButtonElement;
    expect(fulfillBtn1.disabled).toBe(false);
  });

  it("envia status=undefined quando o filtro vira 'Todos' e re-carrega", async () => {
    apiMock.list.mockResolvedValue(pageOf(RECORDS));
    render(<AdminDataRequestsPage />);
    await waitFor(() =>
      expect(screen.getByText("ext@cliente.com")).toBeTruthy(),
    );
    apiMock.list.mockClear();
    apiMock.list.mockResolvedValue(pageOf([]));

    // Radix Select usa role=combobox — clica e seleciona "Todos".
    const statusTrigger = screen.getByTestId("filter-status");
    fireEvent.click(statusTrigger);
    const option = await screen.findByRole("option", { name: "Todos" });
    fireEvent.click(option);

    await waitFor(() =>
      expect(apiMock.list).toHaveBeenCalledWith(
        expect.objectContaining({ status: undefined }),
      ),
    );
  });

  it("modal 'Novo pedido manual' chama createManual e recarrega a lista", async () => {
    apiMock.list.mockResolvedValue(pageOf(RECORDS));
    apiMock.createManual.mockResolvedValue(RECORDS[0]);
    render(<AdminDataRequestsPage />);

    await waitFor(() =>
      expect(screen.getByText("ext@cliente.com")).toBeTruthy(),
    );

    fireEvent.click(screen.getByTestId("btn-new-manual"));
    // Modal abre; preenche email e confirma.
    const emailInput = await screen.findByTestId("manual-email");
    fireEvent.change(emailInput, {
      target: { value: "novo@titular.com" },
    });
    const notesInput = screen.getByTestId("manual-notes");
    fireEvent.change(notesInput, {
      target: { value: "Veio por telefone em 2026-05-15." },
    });

    apiMock.list.mockClear();
    fireEvent.click(screen.getByTestId("btn-create-confirm"));

    await waitFor(() =>
      expect(apiMock.createManual).toHaveBeenCalledWith({
        subject_external_email: "novo@titular.com",
        request_type: "deletion",
        notes: "Veio por telefone em 2026-05-15.",
      }),
    );
    // Recarga após criação.
    await waitFor(() => expect(apiMock.list).toHaveBeenCalled());
    expect(toastMock.success).toHaveBeenCalled();
  });

  it("modal 'Atender' confirma irreversibilidade e chama fulfill", async () => {
    apiMock.list.mockResolvedValue(pageOf(RECORDS));
    apiMock.fulfill.mockResolvedValue({
      ...RECORDS[0],
      status: "fulfilled",
      fulfilled_at: "2026-05-15T11:00:00Z",
      handled_by_id: "pmo-current",
    });
    render(<AdminDataRequestsPage />);

    await waitFor(() =>
      expect(screen.getByText("ext@cliente.com")).toBeTruthy(),
    );

    fireEvent.click(screen.getByTestId("btn-fulfill-rec-1"));

    // O modal deve mostrar alerta de irreversibilidade.
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/irrevers/i)).toBeTruthy();

    apiMock.list.mockClear();
    fireEvent.click(screen.getByTestId("btn-fulfill-confirm"));
    await waitFor(() =>
      expect(apiMock.fulfill).toHaveBeenCalledWith("rec-1"),
    );
    // Recarga após fulfill.
    await waitFor(() => expect(apiMock.list).toHaveBeenCalled());
    expect(toastMock.success).toHaveBeenCalled();
  });
});
