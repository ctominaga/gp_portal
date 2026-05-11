import { describe, expect, it } from "vitest";

import {
  deliverableSchema,
  loginSchema,
  projectCreateSchema,
  reportCreateSchema,
} from "@/lib/schemas";

describe("loginSchema", () => {
  it("aceita e-mail válido + senha", () => {
    expect(loginSchema.parse({ email: "a@b.com", password: "x" })).toEqual({
      email: "a@b.com",
      password: "x",
    });
  });
  it("rejeita e-mail inválido", () => {
    expect(loginSchema.safeParse({ email: "nao-eh-email", password: "x" }).success).toBe(false);
  });
  it("rejeita senha vazia", () => {
    expect(loginSchema.safeParse({ email: "a@b.com", password: "" }).success).toBe(false);
  });
});

describe("projectCreateSchema", () => {
  it("aceita campos mínimos", () => {
    const r = projectCreateSchema.safeParse({ name: "Bradesco", client_name: "Bradesco" });
    expect(r.success).toBe(true);
  });
  it("rejeita name muito curto", () => {
    expect(
      projectCreateSchema.safeParse({ name: "x", client_name: "Bradesco" }).success,
    ).toBe(false);
  });
  it("aceita client_user_email vazio (opcional)", () => {
    expect(
      projectCreateSchema.safeParse({
        name: "P1",
        client_name: "C1",
        client_user_email: "",
      }).success,
    ).toBe(true);
  });
});

describe("reportCreateSchema", () => {
  it("aceita período válido", () => {
    expect(
      reportCreateSchema.safeParse({ period_start: "2026-05-01", period_end: "2026-05-15" }).success,
    ).toBe(true);
  });
  it("rejeita início depois do fim", () => {
    const r = reportCreateSchema.safeParse({
      period_start: "2026-05-15",
      period_end: "2026-05-01",
    });
    expect(r.success).toBe(false);
  });
});

describe("deliverableSchema", () => {
  it("exige título", () => {
    expect(deliverableSchema.safeParse({ title: "" }).success).toBe(false);
    expect(deliverableSchema.safeParse({ title: "A" }).success).toBe(true);
  });
  it("aceita complexity opcional (5 níveis PT-BR após F5.1)", () => {
    for (const c of ["baixa", "baixa-media", "media", "media-alta", "alta"] as const) {
      expect(deliverableSchema.safeParse({ title: "A", complexity: c }).success).toBe(true);
    }
  });
  it("rejeita complexity fora do enum (valores antigos 'low'/'medium'/'high' não passam mais)", () => {
    expect(
      deliverableSchema.safeParse({ title: "A", complexity: "xtreme" as never }).success,
    ).toBe(false);
    expect(
      deliverableSchema.safeParse({ title: "A", complexity: "high" as never }).success,
    ).toBe(false);
  });
  it("aceita campos novos do F5.1 (type, acceptance_criteria, dependencies, status)", () => {
    const r = deliverableSchema.safeParse({
      title: "A",
      type: "code_migration",
      category: "tecnico",
      acceptance_criteria: "notebook em prod",
      dependencies: ["d-000"],
      status: "in_progress",
    });
    expect(r.success).toBe(true);
  });
});
