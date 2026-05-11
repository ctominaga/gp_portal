/**
 * Screenshots para o relatório F3.5. Gera 7 PNGs em ../docs/screenshots/.
 *
 * Mocka todas as chamadas /api/* via page.route() — não precisa de backend.
 */
import path from "node:path";
import { test } from "@playwright/test";

const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");

// Importante: page.route() casa o glob contra a URL completa, não só o path.
// Glob amplo tipo `**/reports/{id}` casa TANTO o backend quanto qualquer rota Next
// terminando no mesmo segmento — devolvendo JSON em vez de HTML. Hoje os specs
// passam por sorte de naming (frontend usa /projetos/.../reports/{id}/edit, backend
// usa /reports/{id}), mas isso é frágil. Scopa todo mock ao host do backend.
// Ver docs/decisoes.md.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PROJECT_ID = "22222222-2222-2222-2222-222222222222";
const BASELINE_ID = "11111111-1111-1111-1111-111111111111";
const REPORT_ID = "44444444-4444-4444-4444-444444444444";

const fakeBaseline = {
  id: BASELINE_ID,
  project_id: PROJECT_ID,
  proposal_id: "33333333-3333-3333-3333-333333333333",
  status: "draft" as const,
  activated_at: null,
  activated_by_id: null,
  payload: {
    summary:
      "Baseline simulado pelo worker_stub para a proposta v1 da Bradesco. 6 entregáveis em 3 fases.",
    phases: [
      { phase_id: "fase-1", name: "Convergência inicial", deliverable_count: 2 },
      { phase_id: "fase-2", name: "Escala", deliverable_count: 2 },
      { phase_id: "fase-3", name: "Fechamento", deliverable_count: 2 },
    ],
    audit: {
      source_proposal_filename: "PT 20251874 - Bradesco - Squad Migração SAS.pdf",
      source_proposal_version: 1,
      extracted_at: "2026-05-07T10:00:00Z",
      engine: "claude",
      route: "headless",
      confidence_score: 0.62,
    },
  },
  created_at: new Date().toISOString(),
  deliverables: [
    {
      id: "d1",
      code: "d-001",
      title: "Migração rotina A → PySpark/Databricks",
      description: null,
      phase: "fase-1",
      category: null,
      complexity: "low" as const,
      source_excerpt:
        "Sprint de convergência inicial, focado em grupos de menor complexidade " +
        "e baixo acoplamento. Ideal para validar o pipeline automatizado e " +
        "estabilizar padrões de conversão.",
      due_date: "2026-06-15",
      order_index: 0,
    },
    {
      id: "d2",
      code: "d-002",
      title: "Migração rotina B → PySpark/Databricks",
      description: null,
      phase: "fase-1",
      category: null,
      complexity: "low" as const,
      source_excerpt:
        "CERM e Outros Riscos possuem baixa densidade e se encaixam na fase de estabilização.",
      due_date: "2026-06-15",
      order_index: 1,
    },
    {
      id: "d3",
      code: "d-003",
      title: "Migração rotina C com lógica intermediária",
      description: null,
      phase: "fase-2",
      category: null,
      complexity: "medium" as const,
      source_excerpt:
        "Equilíbrio entre baixa e média complexidade, com interdependência reduzida.",
      due_date: "2026-07-01",
      order_index: 2,
    },
    {
      id: "d4",
      code: "d-004",
      title: "Migração rotina D com lógica intermediária",
      description: null,
      phase: "fase-2",
      category: null,
      complexity: "medium" as const,
      source_excerpt: "Mantém alta produtividade sem exigir análise manual intensiva.",
      due_date: "2026-07-01",
      order_index: 3,
    },
    {
      id: "d5",
      code: "d-005",
      title: "Migração rotina E (alta densidade lógica)",
      description: null,
      phase: "fase-3",
      category: null,
      complexity: "high" as const,
      source_excerpt:
        "Sprint com grupos de maior densidade lógica, múltiplas dependências, cálculos regulatórios e regras complexas.",
      due_date: "2026-07-15",
      order_index: 4,
    },
    {
      id: "d6",
      code: "d-006",
      title: "Documentação técnica final + handover",
      description: null,
      phase: "fase-3",
      category: null,
      complexity: "medium" as const,
      source_excerpt:
        "Estabilização do ambiente Databricks pós-migração e transferência de conhecimento.",
      due_date: "2026-07-30",
      order_index: 5,
    },
  ],
};

interface ProgressFake {
  deliverable_id: string;
  status: string;
  percent_complete: number;
  revised_date?: string | null;
  deviation_flag?: boolean;
  comment?: string | null;
}

function makeFakeReport(state: {
  rag_prazo: string | null;
  rag_escopo: string | null;
  rag_qualidade: string | null;
  rag_prazo_just?: string;
  rag_escopo_just?: string;
  rag_qualidade_just?: string;
  progresses: ProgressFake[];
}) {
  return {
    id: REPORT_ID,
    project_id: PROJECT_ID,
    period_start: "2026-05-01",
    period_end: "2026-05-15",
    rag_status: null,
    rag_prazo: state.rag_prazo,
    rag_escopo: state.rag_escopo,
    rag_qualidade: state.rag_qualidade,
    rag_prazo_justificativa: state.rag_prazo_just ?? null,
    rag_escopo_justificativa: state.rag_escopo_just ?? null,
    rag_qualidade_justificativa: state.rag_qualidade_just ?? null,
    status: "draft",
    highlights: null,
    next_steps: null,
    notes: null,
    health_score: null,
    created_by_id: "u1",
    created_at: new Date().toISOString(),
    submitted_at: null,
    approved_at: null,
    progresses: state.progresses.map((p) => ({
      deliverable_id: p.deliverable_id,
      status: p.status,
      percent_complete: p.percent_complete,
      comment: p.comment ?? null,
      revised_date: p.revised_date ?? null,
      deviation_flag: p.deviation_flag ?? false,
    })),
    risks: [],
    action_plans: [],
    pending_items: [],
  };
}

test.describe("Screenshots F3.5", () => {
  test.beforeEach(async ({ page, context }) => {
    await context.addInitScript(() => {
      window.localStorage.setItem("jump.token", "fake-token");
    });

    await page.route(`${API}/auth/me`, async (route) => {
      await route.fulfill({
        json: {
          id: "u1",
          name: "GP Bradesco",
          email: "gp.bradesco@jumplabel.com.br",
          role: "GP",
          created_at: new Date().toISOString(),
        },
      });
    });

    await page.route(`${API}/projects/${PROJECT_ID}/active-baseline`, async (r) => {
      await r.fulfill({ json: fakeBaseline });
    });

    await page.route(`${API}/baselines/${BASELINE_ID}`, async (r) => {
      await r.fulfill({ json: fakeBaseline });
    });

    await page.route(`${API}/events/stream`, async (r) => {
      await r.fulfill({
        body: "event: connected\ndata: {}\n\n",
        contentType: "text/event-stream",
      });
    });

    // PATCH em /reports/* — apenas reflete o body para evitar erro de autosave
    await page.route(`${API}/reports/${REPORT_ID}`, async (route) => {
      if (route.request().method() === "PATCH") {
        await route.fulfill({ json: {} });
      } else {
        await route.fallback();
      }
    });
  });

  test("F3.5.1 + 7 + 8: source_excerpt expanded + audit header + 6 deliverables", async ({
    page,
  }) => {
    await page.goto(`/projetos/${PROJECT_ID}/baseline/${BASELINE_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Migração rotina A");
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f35-1-baseline-source-expanded.png"),
      fullPage: true,
    });
  });

  test("F3.5.2: modal de ativação", async ({ page }) => {
    await page.goto(`/projetos/${PROJECT_ID}/baseline/${BASELINE_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Migração rotina A");
    await page.locator('button:has-text("Ativar baseline")').first().click();
    await page.waitForSelector("text=Esta ação não pode ser desfeita");
    await page.waitForTimeout(200);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f35-2-baseline-activate-modal.png"),
      fullPage: true,
    });
  });

  test("F3.5.3+4: RAG por dimensão bloqueando submit (justificativa vazia)", async ({
    page,
  }) => {
    const empty = makeFakeReport({
      rag_prazo: "G",
      rag_escopo: "A",
      rag_qualidade: "R",
      progresses: [],
    });
    await page.route(`${API}/reports/${REPORT_ID}`, async (route) => {
      if (route.request().method() === "GET") await route.fulfill({ json: empty });
      else await route.fulfill({ json: empty });
    });
    await page.goto(`/projetos/${PROJECT_ID}/reports/${REPORT_ID}/edit`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Wizard de report");
    await page.locator('[role="tab"]', { hasText: /RAG/i }).click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f35-3-4-wizard-rag-blocked.png"),
      fullPage: true,
    });
  });

  test("F3.5.3+4: RAG por dimensão preenchido (estado válido)", async ({ page }) => {
    const filled = makeFakeReport({
      rag_prazo: "G",
      rag_escopo: "A",
      rag_qualidade: "R",
      rag_escopo_just:
        "Cliente solicitou inclusão de 2 rotinas extra do GRF (RAW + Provisão).",
      rag_qualidade_just:
        "Bug regulatório encontrado em IRRBB exigiu reabertura da sprint 3.",
      progresses: [],
    });
    await page.route(`${API}/reports/${REPORT_ID}`, async (route) => {
      if (route.request().method() === "GET") await route.fulfill({ json: filled });
      else await route.fulfill({ json: filled });
    });
    await page.goto(`/projetos/${PROJECT_ID}/reports/${REPORT_ID}/edit`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Wizard de report");
    await page.locator('[role="tab"]', { hasText: /RAG/i }).click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f35-3-4-wizard-rag-ok.png"),
      fullPage: true,
    });
  });

  test("F3.5.5: progresso com revised_date e flag de desvio", async ({ page }) => {
    const rep = makeFakeReport({
      rag_prazo: "G",
      rag_escopo: "G",
      rag_qualidade: "G",
      progresses: [
        { deliverable_id: "d1", status: "done", percent_complete: 100, comment: "ok" },
        { deliverable_id: "d2", status: "done", percent_complete: 100 },
        {
          deliverable_id: "d3",
          status: "in_progress",
          percent_complete: 60,
          revised_date: "2026-07-15",
          deviation_flag: true,
          comment: "bloqueio nos acessos do cliente",
        },
        {
          deliverable_id: "d5",
          status: "planned",
          percent_complete: 0,
          revised_date: "2026-07-30",
          deviation_flag: true,
        },
      ],
    });
    await page.route(`${API}/reports/${REPORT_ID}`, async (route) => {
      if (route.request().method() === "GET") await route.fulfill({ json: rep });
      else await route.fulfill({ json: rep });
    });
    await page.goto(`/projetos/${PROJECT_ID}/reports/${REPORT_ID}/edit`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Wizard de report");
    await page.locator('[role="tab"]', { hasText: /Progresso/i }).click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f35-5-wizard-progress-revised.png"),
      fullPage: true,
    });
  });

  test("F3.5.6: critério de aceite confirmado persiste badge no entregável (spec v3.1 §4.2.2)", async ({ page }) => {
    const rep = makeFakeReport({
      rag_prazo: "G",
      rag_escopo: "G",
      rag_qualidade: "G",
      progresses: [
        { deliverable_id: "d1", status: "in_progress", percent_complete: 80 },
        { deliverable_id: "d2", status: "in_progress", percent_complete: 90 },
      ],
    });
    await page.route(`${API}/reports/${REPORT_ID}`, async (route) => {
      if (route.request().method() === "GET") await route.fulfill({ json: rep });
      else await route.fulfill({ json: rep });
    });
    await page.goto(`/projetos/${PROJECT_ID}/reports/${REPORT_ID}/edit`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("text=Wizard de report");
    await page.locator('[role="tab"]', { hasText: /Progresso/i }).click();
    await page.waitForTimeout(300);
    // Mudança no input de % para 100 dispara o dialog
    const percentInputs = page.locator('input[type="number"]');
    await percentInputs.first().fill("100");
    // Mudar o status para "Concluído" via Select
    const selects = page.getByRole("combobox");
    await selects.first().click();
    await page.waitForTimeout(150);
    await page.getByRole("option", { name: /Concluído/i }).click();
    await page.waitForSelector("text=Critério de aceite foi atingido?");
    // Confirma o aceite — modal envia acceptance_confirmed=true ao draft (AJUSTE I)
    await page.getByRole("button", { name: /Sim, concluído/i }).click();
    // Aguarda badge "aceite confirmado" aparecer no card do entregável
    await page.waitForSelector("text=aceite confirmado");
    await page.waitForTimeout(200);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f35-6-wizard-criterio-aceite.png"),
      fullPage: true,
    });
  });
});
