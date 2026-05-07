import { describe, expect, it } from "vitest";

import { aggregateRag, validateRag, worstFilled } from "@/lib/rag";

describe("aggregateRag (worst-of-3)", () => {
  it("retorna null se qualquer dimensão estiver null", () => {
    expect(aggregateRag(null, "G", "G")).toBeNull();
    expect(aggregateRag("G", null, "G")).toBeNull();
    expect(aggregateRag("G", "G", null)).toBeNull();
  });
  it("G/G/G → G", () => {
    expect(aggregateRag("G", "G", "G")).toBe("G");
  });
  it("G/A/G → A", () => {
    expect(aggregateRag("G", "A", "G")).toBe("A");
  });
  it("G/A/R → R (worst-of-3)", () => {
    expect(aggregateRag("G", "A", "R")).toBe("R");
  });
  it("R/A/G ordem não importa → R", () => {
    expect(aggregateRag("R", "A", "G")).toBe("R");
  });
});

describe("worstFilled", () => {
  it("ignora dimensões nulas", () => {
    expect(worstFilled(null, null, null)).toBeNull();
    expect(worstFilled("A", null, null)).toBe("A");
    expect(worstFilled("G", "R", null)).toBe("R");
  });
});

describe("validateRag", () => {
  const baseDraft = {
    rag_prazo: null,
    rag_escopo: null,
    rag_qualidade: null,
    rag_prazo_justificativa: "",
    rag_escopo_justificativa: "",
    rag_qualidade_justificativa: "",
  };

  it("vazio → não ok, 3 dimensões faltando", () => {
    const v = validateRag(baseDraft);
    expect(v.ok).toBe(false);
    expect(v.missingDimensions).toEqual(["prazo", "escopo", "qualidade"]);
    expect(v.aggregate).toBeNull();
  });

  it("3 verdes → ok, sem justificativa", () => {
    const v = validateRag({
      ...baseDraft,
      rag_prazo: "G",
      rag_escopo: "G",
      rag_qualidade: "G",
    });
    expect(v.ok).toBe(true);
    expect(v.aggregate).toBe("G");
    expect(v.missingDimensions).toEqual([]);
    expect(v.missingJustifications).toEqual([]);
  });

  it("uma dimensão Amarela sem justificativa → bloqueia", () => {
    const v = validateRag({
      ...baseDraft,
      rag_prazo: "G",
      rag_escopo: "A",
      rag_qualidade: "G",
    });
    expect(v.ok).toBe(false);
    expect(v.missingJustifications).toEqual(["escopo"]);
  });

  it("uma dimensão Vermelha sem justificativa → bloqueia", () => {
    const v = validateRag({
      ...baseDraft,
      rag_prazo: "R",
      rag_escopo: "G",
      rag_qualidade: "G",
    });
    expect(v.ok).toBe(false);
    expect(v.missingJustifications).toEqual(["prazo"]);
  });

  it("Amarela + justificativa preenchida → ok, agregado A", () => {
    const v = validateRag({
      ...baseDraft,
      rag_prazo: "G",
      rag_escopo: "A",
      rag_qualidade: "G",
      rag_escopo_justificativa: "novo módulo solicitado",
    });
    expect(v.ok).toBe(true);
    expect(v.aggregate).toBe("A");
  });

  it("justificativa apenas com whitespace não conta", () => {
    const v = validateRag({
      ...baseDraft,
      rag_prazo: "G",
      rag_escopo: "A",
      rag_qualidade: "G",
      rag_escopo_justificativa: "    \n  ",
    });
    expect(v.ok).toBe(false);
    expect(v.missingJustifications).toEqual(["escopo"]);
  });

  it("múltiplas dimensões em A/R, faltando justificativa em só uma", () => {
    const v = validateRag({
      ...baseDraft,
      rag_prazo: "A",
      rag_escopo: "R",
      rag_qualidade: "G",
      rag_prazo_justificativa: "atraso na sprint 1",
      // rag_escopo_justificativa em branco → falta
    });
    expect(v.ok).toBe(false);
    expect(v.missingJustifications).toEqual(["escopo"]);
  });

  it("Verde nunca exige justificativa, mesmo com texto presente", () => {
    const v = validateRag({
      ...baseDraft,
      rag_prazo: "G",
      rag_escopo: "G",
      rag_qualidade: "G",
      rag_prazo_justificativa: "(comentário opcional)",
    });
    expect(v.ok).toBe(true);
  });
});
