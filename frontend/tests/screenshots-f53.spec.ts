/**
 * Screenshots F5.3 — Encerramento de projeto + Retrospectiva (v3.1 §10.4).
 *
 * 2 PNGs em ../docs/screenshots/:
 *   f5-3-encerramento-form.png   — Tela /projetos/[id]/encerramento com
 *                                  form preenchido, 2 risks marcados
 *                                  (1 pré-MATERIALIZED + 1 manual).
 *   f5-3-projeto-fechado.png     — Tela /projetos/[id] de projeto CLOSED
 *                                  com banner verde + retrospective.
 *
 * Convenção page.route() escopada ao host do backend (ADR 2026-05-08).
 */
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

async function assertReactUiRendered(page: Page): Promise<void> {
  await expect(
    page.locator("h1"),
    "Nenhum <h1> renderizado — possivelmente page.route() interceptou a " +
      "navegação Next.",
  ).not.toHaveCount(0);
}

const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PROJECT_ID = "55555555-5555-5555-5555-555555555555";
const GP_ID = "u-gp-bradesco";
const RISK_MATERIALIZED = "rr-1-mat";
const RISK_MONITORING = "rr-2-mon";
const RISK_IDENTIFIED = "rr-3-id";

const projectActive = {
  id: PROJECT_ID, name: "SAS→Databricks", client_name: "Bradesco",
  description: "Migração das rotinas SAS de risco e capital para Databricks/PySpark.",
  gp_user_id: GP_ID, client_user_id: null, status: "active",
  started_at: "2026-01-10", ended_at: null, created_at: "2026-01-01",
};

const projectClosed = {
  ...projectActive, status: "closed", ended_at: "2026-05-13",
};

const risks = [
  {
    id: RISK_MATERIALIZED, description: "Bug regulatório IRRBB não-mitigado em sprint 3",
    probability: "alta", impact: "alto", level: "critical",
    mitigation_plan: null, owner_id: null, due_date: null,
    status: "materialized",
  },
  {
    id: RISK_MONITORING, description: "Atraso do time de Auditoria nas validações finais",
    probability: "media", impact: "alto", level: "high",
    mitigation_plan: null, owner_id: null, due_date: null,
    status: "monitoring",
  },
  {
    id: RISK_IDENTIFIED, description: "Disponibilidade limitada da fonte SAS legada",
    probability: "baixa", impact: "medio", level: "low",
    mitigation_plan: null, owner_id: null, due_date: null,
    status: "identified",
  },
];

const retrospective = {
  id: "retro-1", project_id: PROJECT_ID,
  delivered_vs_proposed:
    "9 de 12 entregáveis aprovados foram concluídos no prazo. Sprint 4 " +
    "(Dashboard regulatório) movida para o backlog do próximo ciclo por " +
    "mudança de prioridade do cliente. Migração SAS→Databricks 100% " +
    "operacional em produção.",
  would_do_differently:
    "Criar plano de contingência regulatório no início do projeto, não " +
    "como reação. Alinhar critérios de aceite com a área de Risco antes " +
    "do kickoff. Reservar buffer de 1 sprint para revisão regulatória " +
    "antes da entrega final.",
  client_feedback:
    "Cliente satisfeito com a governança e o ritmo de entregas. Sinalizou " +
    "que esperava mais atenção nos relatórios regulatórios da fase 3 — " +
    "será incluído como item de melhoria para próximos engajamentos.",
  materialized_risks: [
    { risk_id: RISK_MATERIALIZED, comment: "Mitigado via task force regulatório; perdeu 1 sprint mas resolveu sem escalada ao patrocinador." },
  ],
  created_by_id: GP_ID,
  created_at: "2026-05-13T10:00:00Z",
};

test.describe("Screenshots F5.3", () => {
  test.beforeEach(async ({ page, context }) => {
    await context.addInitScript(() => {
      window.localStorage.setItem("jump.token", "fake-token");
    });

    // GP-dono do projeto
    await page.route(`${API}/auth/me`, async (route) => {
      await route.fulfill({
        json: {
          id: GP_ID, name: "Mariana Costa",
          email: "mariana@jumplabel.com.br", role: "GP",
          created_at: new Date().toISOString(),
        },
      });
    });
    await page.route(`${API}/events/stream`, async (r) => {
      await r.fulfill({
        body: "event: connected\ndata: {}\n\n",
        contentType: "text/event-stream",
      });
    });
    await page.route(`${API}/notifications/unread-count`, async (r) => {
      await r.fulfill({ json: { unread: 0 } });
    });
    await page.route(`${API}/notifications`, async (r) => {
      await r.fulfill({ json: [] });
    });
  });

  test("F5.3-A: /projetos/[id]/encerramento — form com 2 risks marcados", async ({ page }) => {
    await page.route(`${API}/projects/${PROJECT_ID}`, async (r) => {
      await r.fulfill({ json: projectActive });
    });
    await page.route(`${API}/projects/${PROJECT_ID}/risks`, async (r) => {
      await r.fulfill({ json: risks });
    });

    await page.goto(`/projetos/${PROJECT_ID}/encerramento`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Encerrar projeto: SAS→Databricks");
    await page.waitForSelector("text=Ação irreversível");

    // Preenche os 3 textareas com exemplos do retrospective acima.
    await page.locator('[data-testid="input-delivered"]').fill(retrospective.delivered_vs_proposed);
    await page.locator('[data-testid="input-would-diff"]').fill(retrospective.would_do_differently);
    await page.locator('[data-testid="input-client-feedback"]').fill(retrospective.client_feedback);

    // GP marca também o risco MONITORING (já vem pré-marcado o MATERIALIZED).
    await page.locator(`[data-testid="risk-checkbox-${RISK_MONITORING}"]`).check();

    // Preenche comment do MATERIALIZED para mostrar UI completa.
    await page.locator(`[data-testid="risk-comment-${RISK_MATERIALIZED}"]`).fill(
      "Mitigado via task force regulatório; perdeu 1 sprint mas resolveu sem escalada.",
    );

    await page.waitForTimeout(400);
    await assertReactUiRendered(page);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f5-3-encerramento-form.png"),
      fullPage: true,
    });
  });

  test("F5.3-B: /projetos/[id] de projeto CLOSED com retrospective", async ({ page }) => {
    await page.route(`${API}/projects/${PROJECT_ID}`, async (r) => {
      await r.fulfill({ json: projectClosed });
    });
    await page.route(`${API}/projects/${PROJECT_ID}/active-baseline`, async (r) => {
      await r.fulfill({ json: null });
    });
    await page.route(`${API}/projects/${PROJECT_ID}/retrospective`, async (r) => {
      await r.fulfill({ json: retrospective });
    });

    await page.goto(`/projetos/${PROJECT_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=SAS→Databricks");
    await page.waitForSelector("text=Projeto encerrado");
    await page.waitForSelector("text=Retrospectiva");
    await page.waitForTimeout(400);
    await assertReactUiRendered(page);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f5-3-projeto-fechado.png"),
      fullPage: true,
    });
  });
});
