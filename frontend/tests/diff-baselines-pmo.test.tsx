/**
 * F5.2 — botões PMO na tela /projetos/[id]/diff.
 * Cobre:
 *  - role=PMO + ScopeChanges PROPOSED → botões aparecem
 *  - role=GP + ScopeChanges PROPOSED → badge "aguardando PMO", sem botões
 *  - modal de approve fecha em cancel
 *  - modal de reject exige justificativa não-vazia
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BaselineDiff, ScopeChange } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "p1" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const apiMock = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: apiMock,
  asApiError: (e: { message: string }) => ({ message: e?.message ?? "x", status: 0 }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const authMock = vi.hoisted(() => ({
  user: { id: "u-pmo", name: "PMO", email: "p@x.com", role: "PMO", created_at: "" },
}));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ ...authMock, loading: false, login: vi.fn(), logout: vi.fn() }),
}));

import ProjectDiffPage from "@/app/projetos/[id]/diff/page";

const baselines = [
  {
    id: "b2", proposal_id: "pp2", status: "draft",
    activated_at: null, created_at: "2026-05-05T10:00:00Z",
    deliverable_count: 7, source_proposal_filename: "v2.pdf", source_proposal_version: 2,
  },
  {
    id: "b1", proposal_id: "pp1", status: "active",
    activated_at: "2026-04-01T10:00:00Z", created_at: "2026-04-01T10:00:00Z",
    deliverable_count: 6, source_proposal_filename: "v1.pdf", source_proposal_version: 1,
  },
];

const diffPayload: BaselineDiff = {
  base_baseline_id: "b1",
  new_baseline_id: "b2",
  added: [],
  removed: [],
  changed: [],
};

const proposedScs: ScopeChange[] = [
  {
    id: "sc-1", project_id: "p1",
    description: "Adicionado: d-007 · Migrar TFS-X",
    baseline_from_id: "b1", baseline_to_id: "b2",
    change_type: "added", deliverable_code: "d-007", status: "proposed",
    requested_at: "2026-05-09T10:00:00Z", decided_at: null, approved_by_id: null,
  },
  {
    id: "sc-2", project_id: "p1",
    description: "Modificado: d-003 (complexity: media → alta)",
    baseline_from_id: "b1", baseline_to_id: "b2",
    change_type: "modified", deliverable_code: "d-003", status: "proposed",
    requested_at: "2026-05-09T10:00:00Z", decided_at: null, approved_by_id: null,
  },
];

function mockGetAll(scs: ScopeChange[]) {
  apiMock.get.mockImplementation((url: string) => {
    if (url.endsWith("/baselines")) return Promise.resolve({ data: baselines });
    if (url.startsWith("/client/diff/")) return Promise.resolve({ data: diffPayload });
    if (url.includes("/scope-changes")) return Promise.resolve({ data: scs });
    return Promise.reject(new Error("unexpected " + url));
  });
}

describe("ProjectDiffPage — F5.2 botões PMO", () => {
  beforeEach(() => {
    apiMock.get.mockReset();
    apiMock.post.mockReset();
    authMock.user = {
      id: "u-pmo", name: "PMO", email: "p@x.com", role: "PMO", created_at: "",
    };
  });

  it("PMO + ScopeChanges PROPOSED → botões Aprovar/Rejeitar aparecem", async () => {
    mockGetAll(proposedScs);
    render(<ProjectDiffPage />);
    await waitFor(() =>
      expect(screen.getByTestId("btn-approve-transition")).toBeTruthy(),
    );
    expect(screen.getByTestId("btn-reject-transition")).toBeTruthy();
    expect(screen.getByText(/aguardando sua decisão/i)).toBeTruthy();
  });

  it("GP + ScopeChanges PROPOSED → badge aguardando PMO, SEM botões", async () => {
    authMock.user = {
      id: "u-gp", name: "GP", email: "g@x.com", role: "GP", created_at: "",
    };
    mockGetAll(proposedScs);
    render(<ProjectDiffPage />);
    await waitFor(() =>
      expect(screen.getByText(/aguardando aprovação do PMO/i)).toBeTruthy(),
    );
    expect(screen.queryByTestId("btn-approve-transition")).toBeNull();
    expect(screen.queryByTestId("btn-reject-transition")).toBeNull();
  });

  it("sem ScopeChanges PROPOSED → nenhuma faixa de transição aparece", async () => {
    mockGetAll([]);
    render(<ProjectDiffPage />);
    await waitFor(() =>
      expect(screen.queryByTestId("btn-approve-transition")).toBeNull(),
    );
    expect(screen.queryByText(/aguardando/i)).toBeNull();
  });

  it("modal de approve abre, cancela limpa estado", async () => {
    mockGetAll(proposedScs);
    render(<ProjectDiffPage />);
    await waitFor(() => screen.getByTestId("btn-approve-transition"));

    act(() => {
      fireEvent.click(screen.getByTestId("btn-approve-transition"));
    });
    // Modal aberto — DialogDescription só existe quando o modal renderiza.
    expect(screen.getByText(/Ação irreversível/i)).toBeTruthy();
    // Cancela
    act(() => {
      fireEvent.click(screen.getByText("Cancelar"));
    });
    // Modal fecha; sem submit
    expect(apiMock.post).not.toHaveBeenCalled();
  });

  it("modal de reject exige justificativa não-vazia para habilitar Confirmar", async () => {
    mockGetAll(proposedScs);
    render(<ProjectDiffPage />);
    await waitFor(() => screen.getByTestId("btn-reject-transition"));

    act(() => {
      fireEvent.click(screen.getByTestId("btn-reject-transition"));
    });
    const confirm = screen.getByTestId("confirm-reject") as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);

    const textarea = screen.getByPlaceholderText(/faltou detalhamento/);
    act(() => {
      fireEvent.change(textarea, { target: { value: "Falta detalhe do critério" } });
    });
    expect(confirm.disabled).toBe(false);
  });
});
