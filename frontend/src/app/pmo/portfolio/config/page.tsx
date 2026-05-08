"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, asApiError } from "@/lib/api";
import type { PortfolioConfig } from "@/lib/types";

const FIELDS: Array<{ key: keyof Omit<PortfolioConfig, "updated_at" | "updated_by_id">; label: string; help: string }> = [
  {
    key: "weight_progress",
    label: "Progresso",
    help: "% de entregáveis concluídos no último report.",
  },
  {
    key: "weight_risks",
    label: "Riscos",
    help: "Penalidade por riscos abertos (critical/high/medium/low).",
  },
  {
    key: "weight_pendings",
    label: "Pendências do cliente",
    help: "Penalidade por item pendente do cliente.",
  },
  {
    key: "weight_schedule",
    label: "Aderência ao prazo",
    help: "% de progressos sem desvio (revised_date == due_date).",
  },
];

export default function PortfolioConfigPage() {
  const [cfg, setCfg] = useState<PortfolioConfig | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const r = await api.get<PortfolioConfig>("/portfolio/config");
        setCfg(r.data);
      } catch (e) {
        toast.error(asApiError(e).message);
      }
    })();
  }, []);

  if (!cfg) {
    return (
      <AppShell>
        <p className="text-sm text-muted-foreground">Carregando…</p>
      </AppShell>
    );
  }

  const total =
    cfg.weight_progress + cfg.weight_risks + cfg.weight_pendings + cfg.weight_schedule;
  const normalize = (v: number) => (total > 0 ? (v / total) * 100 : 25);

  async function save() {
    if (!cfg) return;
    setSaving(true);
    try {
      const r = await api.put<PortfolioConfig>("/portfolio/config", {
        weight_progress: cfg.weight_progress,
        weight_risks: cfg.weight_risks,
        weight_pendings: cfg.weight_pendings,
        weight_schedule: cfg.weight_schedule,
      });
      setCfg(r.data);
      toast.success("Pesos atualizados — Health Score recalcula em tempo real");
    } catch (e) {
      toast.error(asApiError(e).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <p className="text-sm text-muted-foreground">PMO · Configuração</p>
          <h1 className="text-2xl font-semibold tracking-tight">Pesos do Health Score</h1>
        </div>
        <Button asChild variant="ghost">
          <Link href="/pmo/portfolio">← voltar ao portfólio</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>4 dimensões ponderadas</CardTitle>
          <CardDescription>
            Os pesos são normalizados (somam 100%) antes do cálculo. Mudança aqui afeta o
            Health Score de todos os projetos imediatamente.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {FIELDS.map((f) => (
            <div key={f.key} className="grid gap-2 sm:grid-cols-[1fr_120px_120px]">
              <div>
                <Label className="text-base font-medium">{f.label}</Label>
                <p className="text-xs text-muted-foreground">{f.help}</p>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Peso</Label>
                <Input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={cfg[f.key]}
                  onChange={(e) =>
                    setCfg({ ...cfg, [f.key]: Number(e.target.value || 0) } as PortfolioConfig)
                  }
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Normalizado</Label>
                <p className="pt-2 font-mono text-sm">{normalize(cfg[f.key]).toFixed(1)}%</p>
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between border-t pt-4">
            <div className="text-xs text-muted-foreground">
              Soma atual:{" "}
              <strong className="text-foreground">{total.toFixed(2)}</strong>{" "}
              {Math.abs(total - 1) < 0.01 ? "(normalizado)" : `(será normalizado para 1.00)`}
            </div>
            <Button onClick={save} disabled={saving || total <= 0}>
              {saving ? "Salvando…" : "Salvar pesos"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </AppShell>
  );
}
