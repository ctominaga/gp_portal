/**
 * Screenshots para o relatório F3.
 *
 * Mocka todas as chamadas /api/* via page.route() — não precisa de backend.
 * Salva PNGs em ../docs/screenshots/.
 */
import path from "node:path";
import { test } from "@playwright/test";

const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");

const fakeBaseline = {
  id: "11111111-1111-1111-1111-111111111111",
  project_id: "22222222-2222-2222-2222-222222222222",
  proposal_id: "33333333-3333-3333-3333-333333333333",
  status: "draft" as const,
  activated_at: null,
  activated_by_id: null,
  payload: {
    summary:
      "Baseline simulado pelo worker_stub para a proposta v1 da Bradesco. 6 entregáveis em 3 fases.",
    phases: [
      { phase_id: "fase-1", name: "Convergência inicial" },
      { phase_id: "fase-2", name: "Escala" },
      { phase_id: "fase-3", name: "Fechamento" },
    ],
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
        "estabilizar padrões de conversão (notebooks, testes, padrões PySpark) e " +
        "gerar quick wins.",
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
        "Inclui CERM e Outros Riscos, que possuem baixa densidade e se encaixam " +
        "perfeitamente na fase de estabilização.",
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
        "Equilíbrio entre baixa e média complexidade, com interdependência reduzida. " +
        "Excelente sprint para ganhar escala, validar transformações estruturadas e " +
        "consolidar a efetividade do MigrateMind.",
      due_date: "2026-07-01",
      order_index: 2,
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
        "Sprint com grupos de maior densidade lógica, múltiplas dependências, " +
        "cálculos regulatórios e regras complexas. O MigrateMind opera aqui em " +
        "seu máximo potencial, garantindo paralelização, consistência e redução " +
        "significativa do esforço manual.",
      due_date: "2026-07-15",
      order_index: 4,
    },
  ],
};

const fakeReport = {
  id: "44444444-4444-4444-4444-444444444444",
  project_id: "22222222-2222-2222-2222-222222222222",
  period_start: "2026-05-01",
  period_end: "2026-05-15",
  rag_status: "G" as const,
  status: "draft" as const,
  highlights: "Sprint 1 concluída no prazo. 8 das 10 rotinas migradas com sucesso.",
  next_steps: "Iniciar Sprint 2 com Bradesco em 2026-05-16.",
  notes: null,
  health_score: null,
  created_by_id: "u1",
  created_at: new Date().toISOString(),
  submitted_at: null,
  approved_at: null,
  progresses: [
    { deliverable_id: "d1", status: "done" as const, percent_complete: 100, comment: "ok" },
    { deliverable_id: "d2", status: "done" as const, percent_complete: 100, comment: null },
    { deliverable_id: "d3", status: "in_progress" as const, percent_complete: 60, comment: "validação amanhã" },
    { deliverable_id: "d5", status: "planned" as const, percent_complete: 0, comment: null },
  ],
  risks: [
    {
      description: "Acesso ao Databricks de produção pendente desde semana passada.",
      severity: "high" as const,
      owner_id: null,
      due_date: "2026-05-20",
      status: "open" as const,
    },
  ],
  action_plans: [
    {
      description: "Reunião com TI Bradesco quinta-feira para destravar acessos.",
      owner_id: null,
      due_date: "2026-05-15",
      status: "open" as const,
    },
  ],
  pending_items: [
    {
      description: "Credenciais databricks e acesso à VPN",
      owner_party: "client",
      due_date: "2026-05-20",
      status: "open" as const,
    },
  ],
};

test.describe("Screenshots de F3", () => {
  test.beforeEach(async ({ page, context }) => {
    // Mock do auth: backend retorna o user via /auth/me
    await context.addInitScript(() => {
      window.localStorage.setItem("jump.token", "fake-token");
    });

    await page.route("**/auth/me", async (route) => {
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

    await page.route("**/projects/22222222-2222-2222-2222-222222222222/active-baseline", async (r) => {
      await r.fulfill({ json: fakeBaseline });
    });

    await page.route("**/baselines/11111111-1111-1111-1111-111111111111", async (r) => {
      await r.fulfill({ json: fakeBaseline });
    });

    await page.route("**/reports/44444444-4444-4444-4444-444444444444", async (route) => {
      if (route.request().method() === "GET") await route.fulfill({ json: fakeReport });
      else await route.fulfill({ json: fakeReport });
    });

    await page.route("**/events/stream", async (r) => {
      await r.fulfill({ body: "event: connected\ndata: {}\n\n", contentType: "text/event-stream" });
    });
  });

  test("baseline-review", async ({ page }) => {
    await page.goto(
      "/projetos/22222222-2222-2222-2222-222222222222/baseline/11111111-1111-1111-1111-111111111111",
      { waitUntil: "domcontentloaded" },
    );
    await page.waitForSelector("text=Migração rotina A");
    // Expandir um detalhe para mostrar o source_excerpt no screenshot
    await page.locator("summary").first().click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "baseline-review.png"),
      fullPage: true,
    });
  });

  test("report-wizard", async ({ page }) => {
    await page.goto(
      "/projetos/22222222-2222-2222-2222-222222222222/reports/44444444-4444-4444-4444-444444444444/edit",
      { waitUntil: "domcontentloaded" },
    );
    await page.waitForSelector("text=Wizard de report");
    // Vai para a aba de Progresso
    await page.locator('[role="tab"]', { hasText: /Progresso/i }).click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "report-wizard-progress.png"),
      fullPage: true,
    });
    // Aba RAG
    await page.locator('[role="tab"]', { hasText: /RAG/i }).click();
    await page.waitForTimeout(200);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "report-wizard-rag.png"),
      fullPage: true,
    });
  });
});
