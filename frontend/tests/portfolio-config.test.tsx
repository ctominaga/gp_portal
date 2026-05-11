/**
 * Tela /pmo/portfolio/config — 5 dimensões da spec v3.1 §10.3.
 *
 * Cobre:
 *   - renderiza 5 sliders/inputs com labels corretas
 *   - bloqueia salvar quando soma sai de 1.00 ± 0.01
 *   - PUT envia health_score_weights com as 5 chaves
 *   - botão "Restaurar defaults" volta para 35/25/20/10/10
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const apiMock = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: apiMock,
  asApiError: (e: { message: string }) => ({ message: e?.message ?? "x", status: 0 }),
}));

const toastMock = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast: toastMock }));

import PortfolioConfigPage from "@/app/pmo/portfolio/config/page";

const fakeCfg = {
  health_score_weights: {
    rag_avg: 0.35,
    spi: 0.25,
    risk_inverse: 0.20,
    resolution_rate: 0.10,
    stability: 0.10,
  },
  updated_at: "2026-05-08T10:00:00Z",
  updated_by_id: "u-1",
};

function setupGet(cfg = fakeCfg): void {
  apiMock.get.mockResolvedValue({ data: cfg });
}

describe("PortfolioConfigPage (Health Score v3.1 §10.3)", () => {
  it("renderiza 5 dimensões com labels da spec", async () => {
    setupGet();
    render(<PortfolioConfigPage />);
    await waitFor(() =>
      expect(screen.getByText(/5 dimensões ponderadas/i)).toBeTruthy(),
    );
    expect(screen.getByText(/Status RAG médio/i)).toBeTruthy();
    expect(screen.getByText(/^SPI$/i)).toBeTruthy();
    expect(screen.getByText(/Risco inverso/i)).toBeTruthy();
    expect(screen.getByText(/^Resolução$/i)).toBeTruthy();
    expect(screen.getByText(/^Estabilidade$/i)).toBeTruthy();
  });

  it("bloqueia salvar quando soma fora de 1.00 ± 0.01", async () => {
    setupGet();
    apiMock.put.mockResolvedValue({ data: fakeCfg });
    render(<PortfolioConfigPage />);
    await waitFor(() =>
      expect(screen.getByText(/Salvar pesos/i)).toBeTruthy(),
    );
    // Quebra a soma alterando um campo
    const inputs = screen.getAllByRole("spinbutton") as HTMLInputElement[];
    fireEvent.change(inputs[0], { target: { value: "0.99" } });
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /Salvar pesos/i }) as HTMLButtonElement;
      expect(btn.disabled).toBe(true);
    });
    // Mensagem de soma fora da tolerância visível
    expect(screen.getByText(/deve ficar em 1.00/i)).toBeTruthy();
    expect(apiMock.put).not.toHaveBeenCalled();
  });

  it("salva enviando health_score_weights com 5 chaves", async () => {
    setupGet();
    apiMock.put.mockResolvedValue({ data: fakeCfg });
    render(<PortfolioConfigPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Salvar pesos/i })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Salvar pesos/i }));
    await waitFor(() =>
      expect(apiMock.put).toHaveBeenCalledWith(
        "/portfolio/config",
        expect.objectContaining({
          health_score_weights: expect.objectContaining({
            rag_avg: 0.35,
            spi: 0.25,
            risk_inverse: 0.20,
            resolution_rate: 0.10,
            stability: 0.10,
          }),
        }),
      ),
    );
  });

  it("'Restaurar defaults' volta para 35/25/20/10/10", async () => {
    setupGet({
      ...fakeCfg,
      health_score_weights: {
        rag_avg: 0.50,
        spi: 0.30,
        risk_inverse: 0.10,
        resolution_rate: 0.05,
        stability: 0.05,
      },
    });
    render(<PortfolioConfigPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Restaurar defaults/i })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: /Restaurar defaults/i }));
    const inputs = screen.getAllByRole("spinbutton") as HTMLInputElement[];
    expect(Number(inputs[0].value)).toBe(0.35);
    expect(Number(inputs[1].value)).toBe(0.25);
    expect(Number(inputs[2].value)).toBe(0.20);
    expect(Number(inputs[3].value)).toBe(0.10);
    expect(Number(inputs[4].value)).toBe(0.10);
  });
});
