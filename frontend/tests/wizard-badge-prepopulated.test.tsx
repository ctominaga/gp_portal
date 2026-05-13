/**
 * F5.4 commit 3 — badge "Do report anterior" no wizard.
 *
 * O ReportEditPage usa shadcn Tabs com defaultValue="ident"; `<TabsContent>`
 * inativos não renderizam em jsdom (débito F5.1.c documentado em
 * conformidade-v3.1.md). Por isso este teste foca no shape do tipo +
 * lógica condicional do badge, sem montar o page completo. Cobertura
 * visual completa fica para Playwright (Commit 4 do F5.4).
 */
import { render, screen } from "@testing-library/react";
import { History } from "lucide-react";
import { describe, expect, it } from "vitest";

import { Badge } from "@/components/ui/badge";
import type { DeliveryProgress, PendingItem, Risk } from "@/lib/types";

// JSX equivalente ao do wizard real — mesmo data-testid usado no produto.
function PrepopulatedBadge({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <Badge variant="secondary" className="gap-1" data-testid="badge-prepopulated">
      <History className="h-3 w-3" />
      Do report anterior
    </Badge>
  );
}

describe("F5.4 badge 'Do report anterior'", () => {
  it("renderiza quando visible=true", () => {
    render(<PrepopulatedBadge visible={true} />);
    expect(screen.getByTestId("badge-prepopulated")).toBeTruthy();
    expect(screen.getByText(/Do report anterior/)).toBeTruthy();
  });

  it("não renderiza quando visible=false", () => {
    render(<PrepopulatedBadge visible={false} />);
    expect(screen.queryByTestId("badge-prepopulated")).toBeNull();
  });

  it("tipo Risk aceita is_prepopulated opcional", () => {
    // Shape test: garante que o tipo TS está alinhado entre frontend e
    // backend. Se alguém remover o campo do types.ts, o test quebra na
    // compilação (tsc --noEmit roda no CI).
    const risk: Risk = {
      description: "x", probability: "media", impact: "medio",
      mitigation_plan: null, owner_id: null, due_date: null,
      status: "identified", is_prepopulated: true,
    };
    expect(risk.is_prepopulated).toBe(true);

    const riskDefault: Risk = {
      description: "y", probability: "alta", impact: "alto",
      mitigation_plan: null, owner_id: null, due_date: null,
      status: "monitoring",
    };
    // Default omitido — undefined deve ser falsy para a lógica do badge.
    expect(riskDefault.is_prepopulated).toBeUndefined();
  });

  it("tipos PendingItem e DeliveryProgress aceitam is_prepopulated", () => {
    const pi: PendingItem = {
      description: "x", owner_party: "client", due_date: null,
      status: "open", is_prepopulated: true,
    };
    const dp: DeliveryProgress = {
      deliverable_id: "d-1", status: "planned", percent_complete: 0,
      comment: null, revised_date: null, is_prepopulated: true,
    };
    expect(pi.is_prepopulated).toBe(true);
    expect(dp.is_prepopulated).toBe(true);
  });
});
