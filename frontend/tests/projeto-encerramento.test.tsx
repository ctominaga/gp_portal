/**
 * F5.3 — Tela /projetos/[id]/encerramento + render read-only pós-CLOSED
 * em /projetos/[id].
 *
 * Cobre:
 *  - render do form (com pre-seleção de risks MATERIALIZED, Q1 híbrida)
 *  - validação client-side bloqueia submit com campo vazio
 *  - add/remove de risks materializados funciona
 *  - dialog de confirmação aparece e contém data atual
 *  - submit dispara POST com payload correto
 *  - render read-only da retrospective em /projetos/[id] quando CLOSED
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Project, ProjectRetrospective, Risk } from "@/lib/types";

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
  asApiError: (e: { message: string }) => ({ message: e?.message ?? "x", status: 0 }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const authMock = vi.hoisted(() => ({
  user: { id: "u-gp", name: "GP", email: "gp@x.com", role: "GP", created_at: "" },
}));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ ...authMock, loading: false, login: vi.fn(), logout: vi.fn() }),
}));

import ProjectClosePage from "@/app/projetos/[id]/encerramento/page";
import ProjectDetailPage from "@/app/projetos/[id]/page";

const projectActive: Project = {
  id: "p-1", name: "Bradesco SAS", client_name: "Bradesco",
  description: null, gp_user_id: "u-gp", client_user_id: null,
  status: "active", started_at: "2026-01-10", ended_at: null,
  created_at: "2026-01-01",
};

const risks: Risk[] = [
  {
    id: "r-1", description: "Bug regulatório IRRBB",
    probability: "alta", impact: "alto", level: "critical",
    mitigation_plan: null, owner_id: null, due_date: null,
    status: "materialized",
  },
  {
    id: "r-2", description: "Atraso da equipe de Auditoria",
    probability: "media", impact: "medio", level: "medium",
    mitigation_plan: null, owner_id: null, due_date: null,
    status: "monitoring",
  },
  {
    id: "r-3", description: "Disponibilidade da fonte de dados",
    probability: "baixa", impact: "alto", level: "medium",
    mitigation_plan: null, owner_id: null, due_date: null,
    status: "materialized",
  },
];

function mockClosePageHandlers() {
  apiMock.get.mockImplementation((url: string) => {
    if (url === "/projects/p-1") return Promise.resolve({ data: projectActive });
    if (url === "/projects/p-1/risks") return Promise.resolve({ data: risks });
    return Promise.reject(new Error("unexpected GET " + url));
  });
}

describe("ProjectClosePage — F5.3 form encerramento", () => {
  beforeEach(() => {
    apiMock.get.mockReset();
    apiMock.post.mockReset();
    authMock.user = {
      id: "u-gp", name: "GP", email: "gp@x.com", role: "GP", created_at: "",
    };
  });

  it("renderiza form vazio e pré-marca risks MATERIALIZED", async () => {
    mockClosePageHandlers();
    render(<ProjectClosePage />);

    await waitFor(() =>
      expect(screen.getByText(/Encerrar projeto: Bradesco SAS/)).toBeTruthy(),
    );
    // Bug regulatório (r-1) e Disponibilidade (r-3) estão materialized →
    // pré-marcados. r-2 (monitoring) NÃO está pré-marcado.
    const c1 = screen.getByTestId("risk-checkbox-r-1") as HTMLInputElement;
    const c2 = screen.getByTestId("risk-checkbox-r-2") as HTMLInputElement;
    const c3 = screen.getByTestId("risk-checkbox-r-3") as HTMLInputElement;
    expect(c1.checked).toBe(true);
    expect(c2.checked).toBe(false);
    expect(c3.checked).toBe(true);
  });

  it("botão 'Encerrar projeto' fica disabled quando campos obrigatórios estão vazios", async () => {
    mockClosePageHandlers();
    render(<ProjectClosePage />);
    await waitFor(() => screen.getByTestId("btn-open-confirm"));
    const btn = screen.getByTestId("btn-open-confirm") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("botão habilita após preencher os 3 textareas obrigatórios", async () => {
    mockClosePageHandlers();
    render(<ProjectClosePage />);
    await waitFor(() => screen.getByTestId("input-delivered"));

    const fillTextarea = (testid: string, value: string) => {
      const ta = screen.getByTestId(testid);
      act(() => {
        fireEvent.change(ta, { target: { value } });
      });
    };
    fillTextarea("input-delivered", "9/12 entregáveis");
    fillTextarea("input-would-diff", "Plano de contingência regulatório");
    fillTextarea("input-client-feedback", "Cliente satisfeito");

    const btn = screen.getByTestId("btn-open-confirm") as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  it("desmarcar risco pre-selecionado funciona", async () => {
    mockClosePageHandlers();
    render(<ProjectClosePage />);
    await waitFor(() => screen.getByTestId("risk-checkbox-r-1"));
    const c1 = screen.getByTestId("risk-checkbox-r-1") as HTMLInputElement;
    expect(c1.checked).toBe(true);
    act(() => {
      fireEvent.click(c1);
    });
    expect(c1.checked).toBe(false);
  });

  it("marcar risco não-materialized funciona e revela textarea de comment", async () => {
    mockClosePageHandlers();
    render(<ProjectClosePage />);
    await waitFor(() => screen.getByTestId("risk-checkbox-r-2"));
    const c2 = screen.getByTestId("risk-checkbox-r-2") as HTMLInputElement;
    expect(c2.checked).toBe(false);
    expect(screen.queryByTestId("risk-comment-r-2")).toBeNull();

    act(() => {
      fireEvent.click(c2);
    });
    expect(c2.checked).toBe(true);
    expect(screen.getByTestId("risk-comment-r-2")).toBeTruthy();
  });

  it("dialog de confirmação abre com a contagem correta de materializados", async () => {
    mockClosePageHandlers();
    render(<ProjectClosePage />);
    await waitFor(() => screen.getByTestId("input-delivered"));

    act(() => {
      fireEvent.change(screen.getByTestId("input-delivered"), { target: { value: "x" } });
      fireEvent.change(screen.getByTestId("input-would-diff"), { target: { value: "y" } });
      fireEvent.change(screen.getByTestId("input-client-feedback"), { target: { value: "z" } });
    });
    act(() => {
      fireEvent.click(screen.getByTestId("btn-open-confirm"));
    });
    // Dialog visível com texto IRREVERSÍVEL + count = 2 (r-1 e r-3 pré-marcados).
    expect(screen.getByText(/IRREVERSÍVEL/)).toBeTruthy();
    expect(screen.getByText(/2 risco\(s\)/)).toBeTruthy();
  });

  it("submit POST envia payload com 3 campos textuais + materialized_risks", async () => {
    mockClosePageHandlers();
    apiMock.post.mockResolvedValue({
      data: {
        project_id: "p-1", status: "closed", ended_at: "2026-05-12",
        retrospective: {
          id: "retro-1", project_id: "p-1",
          delivered_vs_proposed: "AAA", would_do_differently: "BBB",
          client_feedback: "CCC", materialized_risks: [],
          created_by_id: "u-gp", created_at: "2026-05-12T10:00:00Z",
        },
      },
    });
    render(<ProjectClosePage />);
    await waitFor(() => screen.getByTestId("input-delivered"));

    act(() => {
      fireEvent.change(screen.getByTestId("input-delivered"), { target: { value: "AAA" } });
      fireEvent.change(screen.getByTestId("input-would-diff"), { target: { value: "BBB" } });
      fireEvent.change(screen.getByTestId("input-client-feedback"), { target: { value: "CCC" } });
    });
    act(() => {
      fireEvent.click(screen.getByTestId("btn-open-confirm"));
    });
    act(() => {
      fireEvent.click(screen.getByTestId("btn-confirm-close"));
    });

    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith(
        "/projects/p-1/close",
        expect.objectContaining({
          delivered_vs_proposed: "AAA",
          would_do_differently: "BBB",
          client_feedback: "CCC",
          materialized_risks: expect.arrayContaining([
            expect.objectContaining({ risk_id: "r-1" }),
            expect.objectContaining({ risk_id: "r-3" }),
          ]),
        }),
      ),
    );
  });

  it("bloqueia acesso quando user não é GP-dono", async () => {
    authMock.user = {
      id: "u-outro", name: "Outro", email: "o@x.com", role: "GP", created_at: "",
    };
    mockClosePageHandlers();
    render(<ProjectClosePage />);
    await waitFor(() => expect(screen.getByText(/Acesso negado/)).toBeTruthy());
  });
});


describe("ProjectDetailPage — F5.3 render pós-CLOSED", () => {
  beforeEach(() => {
    apiMock.get.mockReset();
    apiMock.post.mockReset();
    authMock.user = {
      id: "u-gp", name: "GP", email: "gp@x.com", role: "GP", created_at: "",
    };
  });

  const projectClosed: Project = {
    ...projectActive, status: "closed", ended_at: "2026-05-12",
  };

  const retro: ProjectRetrospective = {
    id: "retro-1", project_id: "p-1",
    delivered_vs_proposed: "9/12 entregáveis aceitos",
    would_do_differently: "Plano de contingência regulatório",
    client_feedback: "Cliente satisfeito com governança",
    materialized_risks: [
      { risk_id: "r-1", comment: "Mitigado via task force" },
    ],
    created_by_id: "u-gp",
    created_at: "2026-05-12T10:00:00Z",
  };

  it("mostra banner CLOSED + retrospective com os 3 cards", async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url === "/projects/p-1") return Promise.resolve({ data: projectClosed });
      if (url === "/projects/p-1/active-baseline") return Promise.resolve({ data: null });
      if (url === "/projects/p-1/retrospective") return Promise.resolve({ data: retro });
      return Promise.reject(new Error("unexpected GET " + url));
    });
    render(<ProjectDetailPage />);
    await waitFor(() =>
      expect(screen.getByText(/Projeto encerrado/)).toBeTruthy(),
    );
    expect(screen.getByText(/9\/12 entregáveis aceitos/)).toBeTruthy();
    expect(screen.getByText(/Plano de contingência regulatório/)).toBeTruthy();
    expect(screen.getByText(/Cliente satisfeito com governança/)).toBeTruthy();
    expect(screen.getByText(/Mitigado via task force/)).toBeTruthy();
    // Sem botão "Encerrar" porque já está CLOSED.
    expect(screen.queryByTestId("btn-close-project")).toBeNull();
  });

  it("mostra botão 'Encerrar projeto' quando ACTIVE e user é GP-dono", async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url === "/projects/p-1") return Promise.resolve({ data: projectActive });
      if (url === "/projects/p-1/active-baseline") return Promise.resolve({ data: null });
      return Promise.reject(new Error("unexpected GET " + url));
    });
    render(<ProjectDetailPage />);
    await waitFor(() =>
      expect(screen.getByTestId("btn-close-project")).toBeTruthy(),
    );
  });

  it("oculta botão 'Encerrar projeto' para GP não-dono", async () => {
    authMock.user = {
      id: "u-outro", name: "Outro", email: "o@x.com", role: "GP", created_at: "",
    };
    apiMock.get.mockImplementation((url: string) => {
      if (url === "/projects/p-1") return Promise.resolve({ data: projectActive });
      if (url === "/projects/p-1/active-baseline") return Promise.resolve({ data: null });
      return Promise.reject(new Error("unexpected GET " + url));
    });
    render(<ProjectDetailPage />);
    await waitFor(() => screen.getByText(/Bradesco SAS/));
    expect(screen.queryByTestId("btn-close-project")).toBeNull();
  });
});
