import { describe, expect, it } from "vitest";

import {
  formatBytes,
  humanizeAgo,
  proposalStatusLabel,
  ragColor,
  ragLabel,
  reportStatusLabel,
} from "@/lib/format";

describe("ragColor", () => {
  it.each([
    ["G", "green"],
    ["A", "amber"],
    ["R", "red"],
    [null, "outline"],
  ] as const)("%s -> %s", (status, expected) => {
    expect(ragColor(status)).toBe(expected);
  });
});

describe("ragLabel", () => {
  it("traduz G/A/R para PT-BR", () => {
    expect(ragLabel("G")).toBe("Verde");
    expect(ragLabel("A")).toBe("Amarelo");
    expect(ragLabel("R")).toBe("Vermelho");
  });
  it("retorna — para nulo", () => {
    expect(ragLabel(null)).toBe("—");
    expect(ragLabel(undefined)).toBe("—");
  });
});

describe("proposalStatusLabel", () => {
  it("cobre todos os status", () => {
    expect(proposalStatusLabel("pending_extraction")).toMatch(/extraindo/i);
    expect(proposalStatusLabel("extracted")).toMatch(/extra/i);
    expect(proposalStatusLabel("needs_ocr")).toMatch(/ocr/i);
  });
});

describe("reportStatusLabel", () => {
  it("traduz draft", () => {
    expect(reportStatusLabel("draft")).toBe("Rascunho");
    expect(reportStatusLabel("submitted")).toBe("Submetido");
  });
});

describe("humanizeAgo", () => {
  it("formata segundos / minutos / horas / dias", () => {
    expect(humanizeAgo(45)).toMatch(/s atrás/);
    expect(humanizeAgo(120)).toMatch(/min atrás/);
    expect(humanizeAgo(7200)).toMatch(/h atrás/);
    expect(humanizeAgo(172_800)).toMatch(/d atrás/);
  });
});

describe("formatBytes", () => {
  it("escala B/KB/MB/GB", () => {
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(2 * 1024)).toBe("2.0 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
    expect(formatBytes(2 * 1024 * 1024 * 1024)).toBe("2.0 GB");
  });
});
