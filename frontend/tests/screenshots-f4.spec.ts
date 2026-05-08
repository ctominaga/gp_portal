/**
 * Screenshots para o relatório F4. Gera 5 PNGs em ../docs/screenshots/.
 *
 * Mocka todas as chamadas /api/* via page.route() — não precisa de backend.
 *
 *  1. Dashboard PMO com vários projetos (G/A/R)
 *  2. Aprovação de report com AIInsights e dialog de "pedir revisão" aberto
 *  3. Portal do cliente — visão executiva
 *  4. Configuração de pesos do Health Score
 *  5. Comparação de propostas v1 vs v2
 */
import path from "node:path";
import { test } from "@playwright/test";

const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");

// Importante: Playwright route() casa o GLOB contra a URL completa, não só o path.
// `**/portfolio` casaria TANTO o backend (http://localhost:8000/portfolio) QUANTO a
// página Next (http://localhost:3100/pmo/portfolio) — devolvendo JSON em vez de HTML.
// Por isso scopamos cada mock ao host do backend.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PROJECT_BRADESCO_ID = "22222222-2222-2222-2222-222222222222";
const PROJECT_AMARELO_ID = "33333333-3333-3333-3333-333333333333";
const PROJECT_VERMELHO_ID = "44444444-4444-4444-4444-444444444444";
const REPORT_ID = "55555555-5555-5555-5555-555555555555";
const BASELINE_V1_ID = "66666666-6666-6666-6666-666666666666";
const BASELINE_V2_ID = "77777777-7777-7777-7777-777777777777";

const portfolioOverview = {
  projects: [
    {
      project_id: PROJECT_BRADESCO_ID,
      project_name: "SAS→Databricks",
      client_name: "Bradesco",
      gp_user_id: "u-gp-1",
      gp_name: "Mariana Costa",
      health: {
        project_id: PROJECT_BRADESCO_ID,
        score: 78,
        band: "green",
        components: { progress: 82, risks: 90, pendings: 70, schedule: 70 },
        last_report_id: REPORT_ID,
        last_report_period_end: "2026-05-05",
      },
      last_report_rag: "G",
      open_risks_count: 1,
      open_critical_alerts: 0,
      pending_client_items: 1,
    },
    {
      project_id: PROJECT_AMARELO_ID,
      project_name: "Pipeline ESG",
      client_name: "Itaú",
      gp_user_id: "u-gp-2",
      gp_name: "Lucas Andrade",
      health: {
        project_id: PROJECT_AMARELO_ID,
        score: 55,
        band: "amber",
        components: { progress: 60, risks: 70, pendings: 40, schedule: 50 },
        last_report_id: null,
        last_report_period_end: "2026-04-28",
      },
      last_report_rag: "A",
      open_risks_count: 4,
      open_critical_alerts: 0,
      pending_client_items: 3,
    },
    {
      project_id: PROJECT_VERMELHO_ID,
      project_name: "Migração Mainframe",
      client_name: "Caixa",
      gp_user_id: "u-gp-3",
      gp_name: "Rafael Pereira",
      health: {
        project_id: PROJECT_VERMELHO_ID,
        score: 32,
        band: "red",
        components: { progress: 40, risks: 25, pendings: 30, schedule: 35 },
        last_report_id: null,
        last_report_period_end: "2026-04-21",
      },
      last_report_rag: "R",
      open_risks_count: 7,
      open_critical_alerts: 2,
      pending_client_items: 5,
    },
  ],
  total_projects: 3,
  avg_health_score: 55,
  counts_by_band: { green: 1, amber: 1, red: 1 },
};

const portfolioConfig = {
  weight_progress: 30,
  weight_risks: 25,
  weight_pendings: 20,
  weight_schedule: 25,
  updated_at: "2026-05-01T10:00:00Z",
  updated_by_id: "u-pmo-1",
};

const reportSubmitted = {
  id: REPORT_ID,
  project_id: PROJECT_BRADESCO_ID,
  period_start: "2026-04-29",
  period_end: "2026-05-05",
  rag_status: "A",
  rag_prazo: "A",
  rag_escopo: "G",
  rag_qualidade: "R",
  rag_prazo_justificativa:
    "Sprint 4 atrasou 3 dias por dependência externa do time de Auditoria.",
  rag_escopo_justificativa: null,
  rag_qualidade_justificativa:
    "Bug regulatório em IRRBB exigiu reabertura da sprint 3 e novos testes.",
  status: "submitted",
  highlights:
    "Concluímos a integração da rotina TFS-X com pipeline automatizado. " +
    "8/12 entregáveis avaliados como 'aceito' pela área de negócio.",
  next_steps:
    "Iniciar sprint de testes de carga e revisão dos cenários regulatórios " +
    "junto ao time de Risco de Mercado.",
  notes: null,
  health_score: 58,
  created_by_id: "u-gp-1",
  created_at: "2026-05-05T10:00:00Z",
  submitted_at: "2026-05-05T10:00:00Z",
  approved_at: null,
  progresses: [],
  risks: [
    {
      description: "Bug regulatório IRRBB sem solução há 12 dias",
      severity: "critical",
      owner_id: null,
      due_date: "2026-05-12",
      status: "open",
    },
  ],
  action_plans: [],
  pending_items: [
    {
      description: "Validar layout do dashboard de capital com a área de Risco",
      owner_party: "client",
      due_date: "2026-05-10",
      status: "open",
    },
  ],
};

const projectBradesco = {
  id: PROJECT_BRADESCO_ID,
  name: "SAS→Databricks",
  client_name: "Bradesco",
  description: "Migração das rotinas SAS de risco e capital para Databricks/PySpark.",
  gp_user_id: "u-gp-1",
  client_user_id: "u-cli-1",
  status: "active",
  started_at: "2026-01-10",
  ended_at: null,
  created_at: "2026-01-01",
};

const aiInsights = [
  {
    id: "ins-1",
    scope: "project",
    project_id: PROJECT_BRADESCO_ID,
    report_id: REPORT_ID,
    agent_run_id: null,
    payload: {
      severity: "high",
      headline: "Risco crítico aberto há mais de 10 dias sem mitigação",
      detail:
        "O risco 'Bug regulatório IRRBB' está aberto desde 2026-04-23 sem ação registrada. Padrão de sprint anterior (Q1) sugere que riscos críticos não tratados em 14 dias geram escalonamento ao patrocinador.",
    },
    created_at: "2026-05-05T11:00:00Z",
  },
  {
    id: "ins-2",
    scope: "project",
    project_id: PROJECT_BRADESCO_ID,
    report_id: REPORT_ID,
    agent_run_id: null,
    payload: {
      severity: "medium",
      headline: "Pendência do cliente próxima ao vencimento",
      detail:
        "Item 'Validar layout do dashboard' vence em 5 dias. Bloqueia a release de Sprint 5.",
    },
    created_at: "2026-05-05T11:01:00Z",
  },
];

const clientReport = {
  id: REPORT_ID,
  period_start: "2026-04-29",
  period_end: "2026-05-05",
  rag_status: "A",
  status: "pmo_approved",
  highlights: reportSubmitted.highlights,
  next_steps: reportSubmitted.next_steps,
  submitted_at: reportSubmitted.submitted_at,
  approved_at: null,
  pending_items: [
    {
      description: "Validar layout do dashboard de capital com a área de Risco",
      due_date: "2026-05-10",
      owner_party: "client",
    },
    {
      description: "Aprovar termo aditivo de escopo (rotina TFS-X)",
      due_date: "2026-05-12",
      owner_party: "client",
    },
  ],
};

const clientProjectView = {
  id: PROJECT_BRADESCO_ID,
  name: "SAS→Databricks",
  client_name: "Bradesco",
  status: "active",
  started_at: "2026-01-10",
  latest_rag: "A",
  health_score: 58,
  open_pending_items: 2,
  open_risks_count: 4,
  reports: [
    clientReport,
    {
      ...clientReport,
      id: "old-report-1",
      period_start: "2026-04-22",
      period_end: "2026-04-28",
      rag_status: "G",
      status: "client_released",
      highlights: "Sprint 3 entregue com 100% dos critérios atendidos.",
      next_steps: "Iniciar sprint 4 com foco em testes regulatórios.",
      pending_items: [],
      approved_at: "2026-04-29T10:00:00Z",
    },
  ],
};

const baselinesList = [
  {
    id: BASELINE_V2_ID,
    proposal_id: "prop-v2",
    status: "draft",
    activated_at: null,
    created_at: "2026-04-15T10:00:00Z",
    deliverable_count: 7,
    source_proposal_filename: "PT 20251874 - Bradesco - Squad Migração SAS v2.pdf",
    source_proposal_version: 2,
  },
  {
    id: BASELINE_V1_ID,
    proposal_id: "prop-v1",
    status: "active",
    activated_at: "2026-02-01T10:00:00Z",
    created_at: "2026-01-25T10:00:00Z",
    deliverable_count: 6,
    source_proposal_filename: "PT 20251874 - Bradesco - Squad Migração SAS v1.pdf",
    source_proposal_version: 1,
  },
];

const baselineDiff = {
  base_baseline_id: BASELINE_V1_ID,
  new_baseline_id: BASELINE_V2_ID,
  added: [
    {
      kind: "added",
      code: "d-007",
      title_old: null,
      title_new: "Migração rotina TFS-X (extra solicitado pelo cliente)",
      phase_old: null,
      phase_new: "fase-3",
      complexity_old: null,
      complexity_new: "high",
    },
    {
      kind: "added",
      code: "d-008",
      title_old: null,
      title_new: "Dashboard de capital regulatório",
      phase_old: null,
      phase_new: "fase-3",
      complexity_old: null,
      complexity_new: "medium",
    },
  ],
  removed: [
    {
      kind: "removed",
      code: "d-005",
      title_old: "Conector legado de extração SAS (descontinuado em comum acordo)",
      title_new: null,
      phase_old: "fase-2",
      phase_new: null,
      complexity_old: "low",
      complexity_new: null,
    },
  ],
  changed: [
    {
      kind: "changed",
      code: "d-003",
      title_old: "Migração rotina C com lógica intermediária",
      title_new: "Migração rotina C com lógica intermediária + testes regulatórios",
      phase_old: "fase-2",
      phase_new: "fase-2",
      complexity_old: "medium",
      complexity_new: "high",
    },
  ],
};

test.describe("Screenshots F4", () => {
  test.beforeEach(async ({ page, context }) => {
    await context.addInitScript(() => {
      window.localStorage.setItem("jump.token", "fake-token");
    });

    // /auth/me — papéis variam por tela. Default: PMO
    await page.route(`${API}/auth/me`, async (route) => {
      await route.fulfill({
        json: {
          id: "u-pmo-1",
          name: "PMO Jump",
          email: "pmo@jumplabel.com.br",
          role: "PMO",
          created_at: new Date().toISOString(),
        },
      });
    });

    // SSE
    await page.route(`${API}/events/stream`, async (r) => {
      await r.fulfill({
        body: "event: connected\ndata: {}\n\n",
        contentType: "text/event-stream",
      });
    });

    // Notificações (bell)
    await page.route(`${API}/notifications/unread-count`, async (r) => {
      await r.fulfill({ json: { unread: 2 } });
    });
    await page.route(`${API}/notifications`, async (r) => {
      if (r.request().method() === "GET") {
        await r.fulfill({
          json: [
            {
              id: "n-1",
              kind: "report_submitted",
              title: "Bradesco — novo report submetido",
              body: "Aguardando aprovação do PMO. Período 29/abr → 05/mai.",
              link: `/pmo/reports/${REPORT_ID}/review`,
              read_at: null,
              created_at: new Date().toISOString(),
            },
            {
              id: "n-2",
              kind: "approval_decision",
              title: "Sprint 3 — leitura confirmada pelo cliente",
              body: "Bradesco confirmou leitura em 29/abr.",
              link: null,
              read_at: null,
              created_at: new Date().toISOString(),
            },
          ],
        });
      } else {
        await r.fallback();
      }
    });
  });

  test("F4-1: Dashboard PMO com 3 projetos (G/A/R)", async ({ page }) => {
    await page.route(`${API}/portfolio`, async (r) => {
      await r.fulfill({ json: portfolioOverview });
    });
    await page.goto("/pmo/portfolio", { waitUntil: "domcontentloaded" });
    await page.waitForSelector("text=SAS→Databricks");
    await page.waitForSelector("text=Pipeline ESG");
    await page.waitForSelector("text=Migração Mainframe");
    await page.waitForTimeout(400);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f4-1-pmo-portfolio.png"),
      fullPage: true,
    });
  });

  test("F4-2: Aprovação de report com AIInsights e dialog 'pedir revisão' aberto", async ({
    page,
  }) => {
    await page.route(`${API}/reports/${REPORT_ID}`, async (r) => {
      await r.fulfill({ json: reportSubmitted });
    });
    await page.route(`${API}/projects/${PROJECT_BRADESCO_ID}`, async (r) => {
      await r.fulfill({ json: projectBradesco });
    });
    await page.route(`${API}/reports/${REPORT_ID}/approvals`, async (r) => {
      await r.fulfill({ json: [] });
    });
    await page.route(`${API}/reports/${REPORT_ID}/insights`, async (r) => {
      await r.fulfill({ json: aiInsights });
    });

    await page.goto(`/pmo/reports/${REPORT_ID}/review`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Revisão de report");
    await page.waitForSelector("text=Risco crítico aberto");
    // Abre dialog "pedir revisão" e digita comentário
    await page.locator('button:has-text("Pedir revisão")').first().click();
    await page.waitForSelector("text=Comentário obrigatório");
    await page.locator("textarea").fill(
      "Por favor, detalhar plano de mitigação do bug IRRBB e adicionar marcos de validação " +
        "regulatória até o próximo sprint. Também precisamos de evidência da reabertura " +
        "da sprint 3.",
    );
    await page.waitForTimeout(200);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f4-2-pmo-review-with-comment.png"),
      fullPage: true,
    });
  });

  test("F4-3: Portal do cliente — visão executiva", async ({ page, context }) => {
    // Override /auth/me para retornar CLIENT
    await context.addInitScript(() => {
      window.localStorage.setItem("jump.token", "fake-token-client");
    });
    await page.route(`${API}/auth/me`, async (route) => {
      await route.fulfill({
        json: {
          id: "u-cli-1",
          name: "Patrocinador Bradesco",
          email: "tomada.decisao@bradesco.com.br",
          role: "CLIENT",
          created_at: new Date().toISOString(),
        },
      });
    });
    await page.route(`${API}/client/projects/${PROJECT_BRADESCO_ID}`, async (r) => {
      await r.fulfill({ json: clientProjectView });
    });

    await page.goto(`/portal/projetos/${PROJECT_BRADESCO_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=SAS→Databricks");
    await page.waitForSelector("text=Pendências aguardando você");
    await page.waitForTimeout(400);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f4-3-portal-cliente.png"),
      fullPage: true,
    });
  });

  test("F4-4: Configuração de pesos do Health Score", async ({ page }) => {
    await page.route(`${API}/portfolio/config`, async (r) => {
      await r.fulfill({ json: portfolioConfig });
    });
    await page.goto("/pmo/portfolio/config", { waitUntil: "domcontentloaded" });
    await page.waitForSelector("text=Health Score");
    await page.waitForTimeout(400);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f4-4-health-score-config.png"),
      fullPage: true,
    });
  });

  test("F4-5: Comparação de propostas v1 vs v2", async ({ page }) => {
    await page.route(`${API}/projects/${PROJECT_BRADESCO_ID}/baselines`, async (r) => {
      await r.fulfill({ json: baselinesList });
    });
    await page.route(`${API}/client/diff/${BASELINE_V1_ID}/${BASELINE_V2_ID}`, async (r) => {
      await r.fulfill({ json: baselineDiff });
    });
    // Use GP user para ter permissão no diff
    await page.route(`${API}/auth/me`, async (route) => {
      await route.fulfill({
        json: {
          id: "u-gp-1",
          name: "Mariana Costa",
          email: "mariana@jumplabel.com.br",
          role: "GP",
          created_at: new Date().toISOString(),
        },
      });
    });

    await page.goto(`/projetos/${PROJECT_BRADESCO_ID}/diff`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Comparar baselines");
    await page.waitForSelector("text=Migração rotina TFS-X");
    await page.waitForTimeout(400);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f4-5-diff-propostas.png"),
      fullPage: true,
    });
  });
});
