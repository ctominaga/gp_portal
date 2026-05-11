/**
 * Smoke do tipo TypeScript `PendingItem` (spec v3.1 §4.2.5).
 *
 * Validação de runtime de que objetos literais respeitam a forma esperada,
 * cobrindo a adição de `impact` (opcional) e `created_at` (preenchido pelo
 * backend; cumpre o papel da "Data de abertura" da spec — open_date).
 *
 * Não usa React/jsdom — teste puro de shape (mesmo padrão de
 * action-plan-shape.test.ts, item P3 de hardening de Tabs no jsdom).
 */
import { describe, expect, it } from "vitest";

import type { PendingItem } from "@/lib/types";

describe("PendingItem shape (v3.1 §4.2.5)", () => {
  it("aceita literal com impact + created_at", () => {
    const p: PendingItem = {
      id: "pi-1",
      description: "Validação técnica da rotina IRRBB pendente",
      owner_party: "client",
      due_date: "2026-05-30",
      status: "open",
      impact: "Bloqueia entrega da Sprint 3",
      created_at: "2026-05-08T10:00:00Z",
    };
    expect(p.impact).toContain("Sprint 3");
    expect(p.created_at).toBeDefined();
  });

  it("aceita literal sem impact (campo opcional)", () => {
    const p: PendingItem = {
      description: "Acesso ao Databricks ainda pendente",
      owner_party: "client",
      due_date: null,
      status: "open",
    };
    expect(p.impact).toBeUndefined();
    expect(p.created_at).toBeUndefined();
  });

  it("aceita status resolved (entra em resolution_rate do Health Score)", () => {
    const p: PendingItem = {
      description: "Aprovação do layout",
      owner_party: "client",
      due_date: null,
      status: "resolved",
      impact: null,
    };
    expect(p.status).toBe("resolved");
  });
});
