/**
 * Screenshots F5.2 — Versionamento de escopo (v3.1 §10.5).
 *
 * 2 PNGs em ../docs/screenshots/:
 *   f5-2-scope-changes-list.png       — Rota /pmo/scope-changes com 2 projetos
 *   f5-2-portfolio-with-badge.png     — Dashboard PMO com badge condicional
 *
 * Convenção page.route() escopada ao host do backend (ADR 2026-05-08).
 */
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

async function assertReactUiRendered(page: Page): Promise<void> {
  await expect(
    page.locator("h1"),
    "Nenhum <h1> renderizado — possivelmente page.route() interceptou a " +
      "navegação Next. Confira escopo dos mocks.",
  ).not.toHaveCount(0);
}

const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PROJECT_BRADESCO_ID = "22222222-2222-2222-2222-222222222222";
const PROJECT_ITAU_ID = "33333333-3333-3333-3333-333333333333";
const PROJECT_CAIXA_ID = "44444444-4444-4444-4444-444444444444";
const BASELINE_BRADESCO_V2 = "aaaa1111-aaaa-1111-aaaa-111111111111";
const BASELINE_ITAU_V2 = "bbbb2222-bbbb-2222-bbbb-222222222222";

const PROPOSED_SCOPE_CHANGES = [
  // Bradesco — 3 mudanças (1 add, 1 mod, 1 rem)
  {
    id: "sc-1", project_id: PROJECT_BRADESCO_ID,
    description: "Adicionado: d-007 · Migração rotina TFS-X",
    baseline_from_id: "v1-brad", baseline_to_id: BASELINE_BRADESCO_V2,
    change_type: "added", deliverable_code: "d-007", status: "proposed",
    requested_at: "2026-05-09T10:00:00Z",
    decided_at: null, approved_by_id: null,
  },
  {
    id: "sc-2", project_id: PROJECT_BRADESCO_ID,
    description: "Modificado: d-003 (complexity: media → alta)",
    baseline_from_id: "v1-brad", baseline_to_id: BASELINE_BRADESCO_V2,
    change_type: "modified", deliverable_code: "d-003", status: "proposed",
    requested_at: "2026-05-09T10:00:00Z",
    decided_at: null, approved_by_id: null,
  },
  {
    id: "sc-3", project_id: PROJECT_BRADESCO_ID,
    description: "Removido: d-005 · Conector legado SAS",
    baseline_from_id: "v1-brad", baseline_to_id: BASELINE_BRADESCO_V2,
    change_type: "removed", deliverable_code: "d-005", status: "proposed",
    requested_at: "2026-05-09T10:00:00Z",
    decided_at: null, approved_by_id: null,
  },
  // Itaú — 1 mudança (1 add)
  {
    id: "sc-4", project_id: PROJECT_ITAU_ID,
    description: "Adicionado: d-101 · Dashboard ESG consolidado",
    baseline_from_id: "v1-itau", baseline_to_id: BASELINE_ITAU_V2,
    change_type: "added", deliverable_code: "d-101", status: "proposed",
    requested_at: "2026-05-10T14:00:00Z",
    decided_at: null, approved_by_id: null,
  },
];

const PROJECTS = [
  {
    id: PROJECT_BRADESCO_ID, name: "SAS→Databricks", client_name: "Bradesco",
    description: null, gp_user_id: "u-gp-1", client_user_id: null,
    status: "active", started_at: "2026-01-10", ended_at: null,
    created_at: "2026-01-01",
  },
  {
    id: PROJECT_ITAU_ID, name: "Pipeline ESG", client_name: "Itaú",
    description: null, gp_user_id: "u-gp-2", client_user_id: null,
    status: "active", started_at: "2026-02-01", ended_at: null,
    created_at: "2026-01-15",
  },
  {
    id: PROJECT_CAIXA_ID, name: "Migração Mainframe", client_name: "Caixa",
    description: null, gp_user_id: "u-gp-3", client_user_id: null,
    status: "active", started_at: "2026-03-01", ended_at: null,
    created_at: "2026-02-15",
  },
];

// Portfolio overview com `pending_transitions_count` divergente entre projetos —
// Bradesco tem 3, Itaú tem 1, Caixa não tem. UI deve renderizar badge só nos 2
// primeiros (renderização condicional do F5.2 commit 4).
const PORTFOLIO_OVERVIEW = {
  projects: [
    {
      project_id: PROJECT_BRADESCO_ID, project_name: "SAS→Databricks",
      client_name: "Bradesco", gp_user_id: "u-gp-1", gp_name: "Mariana Costa",
      health: {
        project_id: PROJECT_BRADESCO_ID, score: 79.6, band: "green",
        components: { rag_avg: 83, spi: 82, risk_inverse: 75, resolution_rate: 80, stability: 70 },
        weights_applied: { rag_avg: 0.35, spi: 0.25, risk_inverse: 0.20, resolution_rate: 0.10, stability: 0.10 },
        last_report_id: "r-1", last_report_period_end: "2026-05-05",
      },
      last_report_rag: "G",
      open_risks_count: 1, open_critical_alerts: 0, pending_client_items: 1,
      pending_transitions_count: 3,
    },
    {
      project_id: PROJECT_ITAU_ID, project_name: "Pipeline ESG",
      client_name: "Itaú", gp_user_id: "u-gp-2", gp_name: "Lucas Andrade",
      health: {
        project_id: PROJECT_ITAU_ID, score: 53.5, band: "amber",
        components: { rag_avg: 50, spi: 60, risk_inverse: 55, resolution_rate: 50, stability: 50 },
        weights_applied: { rag_avg: 0.35, spi: 0.25, risk_inverse: 0.20, resolution_rate: 0.10, stability: 0.10 },
        last_report_id: null, last_report_period_end: "2026-04-28",
      },
      last_report_rag: "A",
      open_risks_count: 4, open_critical_alerts: 0, pending_client_items: 3,
      pending_transitions_count: 1,
    },
    {
      project_id: PROJECT_CAIXA_ID, project_name: "Migração Mainframe",
      client_name: "Caixa", gp_user_id: "u-gp-3", gp_name: "Rafael Pereira",
      health: {
        project_id: PROJECT_CAIXA_ID, score: 27.8, band: "red",
        components: { rag_avg: 20, spi: 35, risk_inverse: 25, resolution_rate: 40, stability: 30 },
        weights_applied: { rag_avg: 0.35, spi: 0.25, risk_inverse: 0.20, resolution_rate: 0.10, stability: 0.10 },
        last_report_id: null, last_report_period_end: "2026-04-21",
      },
      last_report_rag: "R",
      open_risks_count: 7, open_critical_alerts: 2, pending_client_items: 5,
      pending_transitions_count: 0,  // sem badge — renderização condicional
    },
  ],
  total_projects: 3,
  avg_health_score: 53.6,
  counts_by_band: { green: 1, amber: 1, red: 1 },
};

test.describe("Screenshots F5.2", () => {
  test.beforeEach(async ({ page, context }) => {
    await context.addInitScript(() => {
      window.localStorage.setItem("jump.token", "fake-token");
    });

    // PMO por default
    await page.route(`${API}/auth/me`, async (route) => {
      await route.fulfill({
        json: {
          id: "u-pmo-1", name: "PMO Jump",
          email: "pmo@jumplabel.com.br", role: "PMO",
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

  test("F5.2-A: /pmo/scope-changes lista portfólio-wide com 4 mudanças de 2 projetos", async ({
    page,
  }) => {
    await page.route(new RegExp(`${API}/scope-changes.*`), async (r) => {
      await r.fulfill({ json: PROPOSED_SCOPE_CHANGES });
    });
    await page.route(`${API}/projects`, async (r) => {
      await r.fulfill({ json: PROJECTS });
    });

    await page.goto("/pmo/scope-changes", { waitUntil: "domcontentloaded" });
    await page.waitForSelector("text=Transições de baseline pendentes");
    await page.waitForSelector("text=SAS→Databricks");
    await page.waitForSelector("text=Pipeline ESG");
    await page.waitForTimeout(400);
    await assertReactUiRendered(page);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f5-2-scope-changes-list.png"),
      fullPage: true,
    });
  });

  test("F5.2-B: /pmo/portfolio com badge 'N transições pendentes' (condicional)", async ({
    page,
  }) => {
    await page.route(`${API}/portfolio`, async (r) => {
      await r.fulfill({ json: PORTFOLIO_OVERVIEW });
    });

    await page.goto("/pmo/portfolio", { waitUntil: "domcontentloaded" });
    await page.waitForSelector("text=SAS→Databricks");
    await page.waitForSelector("text=Pipeline ESG");
    await page.waitForSelector("text=Migração Mainframe");
    // Badges aparecem em Bradesco (3) e Itaú (1), mas NÃO em Caixa (0).
    await page.waitForSelector("text=3 transição(ões) pendente(s)");
    await page.waitForSelector("text=1 transição(ões) pendente(s)");
    await page.waitForTimeout(400);
    await assertReactUiRendered(page);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f5-2-portfolio-with-badge.png"),
      fullPage: true,
    });
  });
});
