import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HealthGauge } from "@/components/health-gauge";

describe("HealthGauge", () => {
  it("renderiza o número arredondado e a label da banda", () => {
    const { container, getByText } = render(
      <HealthGauge score={72.4} band="green" />,
    );
    expect(getByText("72")).toBeTruthy();
    expect(getByText("Saudável")).toBeTruthy();
    // Tem dois <path> (fundo + preenchido)
    expect(container.querySelectorAll("path").length).toBe(2);
  });

  it("score 0 não renderiza arco preenchido (apenas o fundo)", () => {
    const { container } = render(<HealthGauge score={0} band="red" />);
    expect(container.querySelectorAll("path").length).toBe(1);
  });

  it("aplica classe vermelha quando band=red e exibe Crítico", () => {
    const { getByText, container } = render(
      <HealthGauge score={20} band="red" />,
    );
    expect(getByText("Crítico")).toBeTruthy();
    // texto do score com classe text-red-700
    const numText = container.querySelector("text");
    expect(numText?.getAttribute("class")).toMatch(/red/);
  });

  it("respeita size lg gerando svg maior", () => {
    const { container: small } = render(<HealthGauge score={50} band="amber" size="sm" />);
    const { container: large } = render(<HealthGauge score={50} band="amber" size="lg" />);
    const smW = parseInt(small.querySelector("svg")!.getAttribute("width")!, 10);
    const lgW = parseInt(large.querySelector("svg")!.getAttribute("width")!, 10);
    expect(lgW).toBeGreaterThan(smW);
  });

  it("clampeia score acima de 100 sem quebrar render", () => {
    const { getByText } = render(<HealthGauge score={150} band="green" />);
    expect(getByText("150")).toBeTruthy();
  });
});
