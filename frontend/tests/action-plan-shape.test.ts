/**
 * Smoke do tipo TypeScript `ActionPlan` (spec v3.1 §4.2.4).
 *
 * Validação de runtime de que objetos literais respeitam a forma esperada,
 * cobrindo a adição de `objective` + `linked_risk_id` + `linked_deliverable_id`
 * + `linked_risk_description`/`linked_deliverable_title` (expansão do backend).
 *
 * Não usa React/jsdom — teste puro de shape para ficar imune ao caveat de
 * Radix Tabs no jsdom isolado (P3 hardening item).
 */
import { describe, expect, it } from "vitest";

import type { ActionPlan } from "@/lib/types";

describe("ActionPlan shape (v3.1 §4.2.4)", () => {
  it("aceita literal com objective + ambas as vinculações + expansão", () => {
    const ap: ActionPlan = {
      id: "ap-1",
      description: "contratar consultoria externa",
      objective: "reduzir probabilidade do risco IRRBB",
      owner_id: null,
      due_date: "2026-05-30",
      status: "open",
      linked_risk_id: "r-1",
      linked_deliverable_id: "d-001",
      linked_risk_description: "Bug regulatório IRRBB sem solução",
      linked_deliverable_title: "Migração de IRRBB para PySpark/Databricks",
    };
    expect(ap.objective.length).toBeGreaterThan(0);
    expect(ap.linked_risk_id).toBe("r-1");
    expect(ap.linked_deliverable_id).toBe("d-001");
    expect(ap.linked_risk_description).toContain("IRRBB");
  });

  it("aceita ActionPlan sem nenhuma vinculação (ambos os linked_* null)", () => {
    const ap: ActionPlan = {
      description: "documentar processo",
      objective: "reduzir bus factor",
      owner_id: null,
      due_date: null,
      status: "open",
      linked_risk_id: null,
      linked_deliverable_id: null,
    };
    expect(ap.linked_risk_id).toBeNull();
    expect(ap.linked_deliverable_id).toBeNull();
  });

  it("aceita ActionPlan com apenas uma das vinculações", () => {
    const a: ActionPlan = {
      description: "revisar contrato",
      objective: "alinhar premissa de validação em 5 dias",
      owner_id: null,
      due_date: null,
      status: "in_progress",
      linked_risk_id: null,
      linked_deliverable_id: "d-007",
    };
    expect(a.linked_deliverable_id).toBe("d-007");
    expect(a.linked_risk_id).toBeNull();
  });
});
