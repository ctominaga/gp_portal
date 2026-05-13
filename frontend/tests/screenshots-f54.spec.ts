/**
 * Screenshots F5.4 — Modo de Report Assistido por IA (v3.1 §10.2).
 *
 * 3 PNGs em ../docs/screenshots/:
 *   f5-4-reports-novo-radio.png  — /reports/novo com radio dual + período
 *                                  preenchido (pré-popular pré-marcado).
 *   f5-4-wizard-com-badge.png    — Wizard /reports/[rid]/edit com badge
 *                                  "Do report anterior" visível em
 *                                  DeliveryProgress da tab default.
 *   f5-4-conflito-modal.png      — Modal 409 quando período já existe,
 *                                  com botão "Abrir report existente".
 */
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

async function assertReactUiRendered(page: Page): Promise<void> {
  await expect(
    page.locator("h1"),
    "Nenhum <h1> renderizado — page.route() pode ter interceptado a navegação.",
  ).not.toHaveCount(0);
}

const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PROJECT_ID = "66666666-6666-6666-6666-666666666666";
const REPORT_ID_EXISTING = "77777777-7777-7777-7777-777777777777";
const REPORT_ID_NEW = "88888888-8888-8888-8888-888888888888";
const GP_ID = "u-gp-f54";

const project = {
  id: PROJECT_ID, name: "SAS→Databricks", client_name: "Bradesco",
  description: null, gp_user_id: GP_ID, client_user_id: null,
  status: "active", started_at: "2026-01-10", ended_at: null,
  created_at: "2026-01-01",
};

const previousReports = [
  {
    id: REPORT_ID_EXISTING, project_id: PROJECT_ID,
    period_start: "2026-04-29", period_end: "2026-05-05",
    rag_status: "A", status: "client_released",
    created_at: "2026-05-05T10:00:00Z", submitted_at: "2026-05-05T11:00:00Z",
  },
];

const prepopulatedReport = {
  id: REPORT_ID_NEW, project_id: PROJECT_ID,
  period_start: "2026-05-06", period_end: "2026-05-19",
  rag_status: null, rag_prazo: null, rag_escopo: null, rag_qualidade: null,
  rag_prazo_justificativa: null, rag_escopo_justificativa: null,
  rag_qualidade_justificativa: null, status: "draft",
  highlights: null, next_steps: null, notes: null, health_score: null,
  created_by_id: GP_ID, created_at: "2026-05-13T10:00:00Z",
  submitted_at: null, approved_at: null,
  progresses: [
    {
      id: "p-1", deliverable_id: "d-001",
      status: "planned", percent_complete: 0,
      comment: null, revised_date: null, deviation_flag: false,
      acceptance_confirmed: null, is_prepopulated: true,
    },
  ],
  risks: [
    {
      id: "r-1", description: "Bug regulatório IRRBB sem mitigação",
      probability: "alta", impact: "alto", level: "critical",
      mitigation_plan: null, owner_id: null, due_date: null,
      status: "monitoring", is_prepopulated: true,
    },
  ],
  action_plans: [],
  pending_items: [],
};

const baseline = {
  id: "b-1", project_id: PROJECT_ID, proposal_id: "pp-1", status: "active",
  activated_at: "2026-02-01T10:00:00Z", activated_by_id: GP_ID, payload: {},
  created_at: "2026-01-25T10:00:00Z",
  deliverables: [
    {
      id: "d-001", baseline_id: "b-1", code: "d-001",
      title: "Migração rotina C", description: null, phase: "fase-1",
      category: null, complexity: null, type: null, source_excerpt: null,
      due_date: "2026-05-10", acceptance_criteria: null,
      dependencies: [], status: "not_started", order_index: 0,
      created_at: "",
    },
  ],
};

test.describe("Screenshots F5.4", () => {
  test.beforeEach(async ({ page, context }) => {
    await context.addInitScript(() => {
      window.localStorage.setItem("jump.token", "fake-token");
    });
    await page.route(`${API}/auth/me`, async (r) => {
      await r.fulfill({
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

  test("F5.4-A: /reports/novo com radio dual + pré-popular pré-marcado", async ({ page }) => {
    await page.route(`${API}/projects/${PROJECT_ID}/reports`, async (r) => {
      await r.fulfill({ json: previousReports });
    });

    await page.goto(`/projetos/${PROJECT_ID}/reports/novo`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Novo report");
    await page.waitForSelector("text=Pré-popular do report anterior");
    // Preenche o período para o screenshot ficar realista.
    await page.locator("#period_start").fill("2026-05-06");
    await page.locator("#period_end").fill("2026-05-19");
    await page.waitForTimeout(400);
    await assertReactUiRendered(page);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f5-4-reports-novo-radio.png"),
      fullPage: true,
    });
  });

  test("F5.4-B: wizard com badge 'Do report anterior' em DeliveryProgress", async ({
    page,
  }) => {
    await page.route(`${API}/reports/${REPORT_ID_NEW}`, async (r) => {
      await r.fulfill({ json: prepopulatedReport });
    });
    await page.route(`${API}/projects/${PROJECT_ID}/active-baseline`, async (r) => {
      await r.fulfill({ json: baseline });
    });

    await page.goto(`/projetos/${PROJECT_ID}/reports/${REPORT_ID_NEW}/edit`, {
      waitUntil: "domcontentloaded",
    });
    // Tab default é "ident"; navega para "prog" pra mostrar o badge.
    await page.waitForSelector("text=Identificação");
    await page.locator('button[role="tab"]:has-text("Progresso")').click();
    await page.waitForSelector("text=Migração rotina C");
    await page.waitForSelector("text=Do report anterior");
    await page.waitForTimeout(400);
    await assertReactUiRendered(page);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f5-4-wizard-com-badge.png"),
      fullPage: true,
    });
  });

  test("F5.4-C: modal 409 quando período duplicado + link 'Abrir report existente'", async ({
    page,
  }) => {
    await page.route(`${API}/projects/${PROJECT_ID}/reports`, async (r) => {
      await r.fulfill({ json: previousReports });
    });
    await page.route(
      `${API}/projects/${PROJECT_ID}/reports/prepopulate`,
      async (r) => {
        await r.fulfill({
          status: 409,
          json: {
            detail:
              `Já existe report no período 2026-04-29–2026-05-05. ` +
              `Acesse-o em /reports/${REPORT_ID_EXISTING}.`,
          },
        });
      },
    );

    await page.goto(`/projetos/${PROJECT_ID}/reports/novo`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Pré-popular do report anterior");
    await page.locator("#period_start").fill("2026-04-29");
    await page.locator("#period_end").fill("2026-05-05");
    await page.locator('[data-testid="btn-submit"]').click();
    await page.waitForSelector("text=Report já existe nesse período");
    await page.waitForTimeout(400);
    await assertReactUiRendered(page);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f5-4-conflito-modal.png"),
      fullPage: true,
    });
  });
});
