/**
 * E2E mínima do fluxo do GP: login → criar projeto → upload proposta →
 * aguardar extração (worker stub) → revisar baseline → ativar → criar report
 * → preencher 7 seções → submit.
 *
 * Pré-requisitos:
 *   - backend rodando em PLAYWRIGHT_API_URL (default http://localhost:8000)
 *     com STUB_WORKER_ENABLED=true e STUB_WORKER_DELAY_S<=3
 *   - frontend rodando em PLAYWRIGHT_BASE_URL (default http://localhost:13000)
 *     OU 3000 (next dev)
 *   - usuário GP semeado: gp.bradesco@jumplabel.com.br / JumpDev123!
 *     (criado pelo seed do backend)
 *
 * Como rodar:
 *   cd backend && docker compose up -d  # ou uvicorn local com STUB_WORKER_DELAY_S=2
 *   cd frontend && npm run dev          # noutro terminal
 *   npx playwright install chromium     # uma vez
 *   npx playwright test
 */
import { test, expect } from "@playwright/test";

const GP_EMAIL = process.env.GP_EMAIL ?? "gp.bradesco@jumplabel.com.br";
const GP_PASSWORD = process.env.GP_PASSWORD ?? "JumpDev123!";

test("fluxo completo do GP — login → submit do report", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(GP_EMAIL);
  await page.getByLabel("Senha").fill(GP_PASSWORD);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL("**/dashboard", { timeout: 10000 });

  // Cria projeto
  await page.getByRole("link", { name: /Novo projeto/i }).first().click();
  await page.waitForURL("**/projetos/novo");
  await page.getByLabel("Nome do projeto *").fill(`E2E Bradesco ${Date.now()}`);
  await page.getByLabel("Cliente *").fill("Bradesco E2E");
  await page.getByRole("button", { name: /Criar projeto/i }).click();
  await page.waitForURL(/\/projetos\/[0-9a-f-]+$/, { timeout: 10000 });

  // Upload proposta
  await page.getByRole("link", { name: /Enviar proposta/i }).click();
  await page.waitForURL(/\/proposta\/nova$/);

  const fileBytes = Buffer.from(
    "%PDF-1.4 e2e fake content " + "x".repeat(2048),
    "utf-8",
  );
  await page.setInputFiles('input[type="file"]', {
    name: "proposta-e2e.pdf",
    mimeType: "application/pdf",
    buffer: fileBytes,
  });
  await page.getByRole("button", { name: /Enviar e extrair/i }).click();

  // Espera a transição extracted (worker stub)
  await expect(page.getByText(/Baseline pronto/i)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: /Revisar baseline/i }).click();
  await page.waitForURL(/\/baseline\//);

  // Ativar baseline (confirm dialog do navegador)
  page.on("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: /Ativar baseline/i }).click();
  await page.waitForURL(/\/projetos\/[0-9a-f-]+$/, { timeout: 10_000 });

  // Criar report
  await page.getByRole("link", { name: /Novo report/i }).click();
  await page.waitForURL(/\/reports\/novo$/);
  const today = new Date().toISOString().slice(0, 10);
  const future = new Date(Date.now() + 14 * 86_400_000).toISOString().slice(0, 10);
  await page.getByLabel("Início *").fill(today);
  await page.getByLabel("Fim *").fill(future);
  await page.getByRole("button", { name: /Criar e abrir wizard/i }).click();
  await page.waitForURL(/\/reports\/.+\/edit$/);

  // RAG verde
  await page.getByRole("tab", { name: /RAG/i }).click();
  await page.getByRole("button", { name: "Verde" }).click();

  // Destaques
  await page.getByRole("tab", { name: /Destaques/i }).click();
  await page.getByLabel("Destaques").fill("Tudo ok no piloto E2E.");
  await page.getByLabel("Próximos passos").fill("Continuar conforme plano.");

  // Aguarda autosave (debounce 800ms + render)
  await expect(page.getByText(/salvo/i)).toBeVisible({ timeout: 5000 });

  // Submeter
  await page.getByRole("button", { name: /Submeter report/i }).click();
  await page.waitForURL(/\/reports$/, { timeout: 10_000 });
  await expect(page.getByText("Submetido")).toBeVisible();
});
