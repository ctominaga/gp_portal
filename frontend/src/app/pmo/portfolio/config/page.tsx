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
import type {
  HealthScoreWeightKey,
  HealthScoreWeights,
  PortfolioConfig,
} from "@/lib/types";

// Defaults da spec v3.1 §10.3
const DEFAULT_WEIGHTS: HealthScoreWeights = {
  rag_avg: 0.35,
  spi: 0.25,
  risk_inverse: 0.20,
  resolution_rate: 0.10,
  stability: 0.10,
};

const FIELDS: Array<{
  key: HealthScoreWeightKey;
  label: string;
  help: string;
}> = [
  {
    key: "rag_avg",
    label: "Status RAG médio",
    help: "Média das 3 dimensões do último report (Prazo, Escopo, Qualidade).",
  },
  {
    key: "spi",
    label: "SPI",
    help: "Progresso real vs. planejado das entregas (Schedule Performance Index).",
  },
  {
    key: "risk_inverse",
    label: "Risco inverso",
    help: "Penalidade pelos riscos abertos no último report (ponderada por nível).",
  },
  {
    key: "resolution_rate",
    label: "Resolução",
    help: "Pendências resolvidas vs. abertas no período.",
  },
  {
    key: "stability",
    label: "Estabilidade",
    help: "Quantos reports consecutivos no mesmo status RAG agregado.",
  },
];

export default function PortfolioConfigPage() {
  const [cfg, setCfg] = useState<PortfolioConfig | null>(null);
  const [weights, setWeights] = useState<HealthScoreWeights>(DEFAULT_WEIGHTS);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const r = await api.get<PortfolioConfig>("/portfolio/config");
        setCfg(r.data);
        setWeights({ ...DEFAULT_WEIGHTS, ...r.data.health_score_weights });
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

  const total = FIELDS.reduce((acc, f) => acc + (weights[f.key] || 0), 0);
  const normalize = (v: number) => (total > 0 ? (v / total) * 100 : 20);
  const withinTolerance = Math.abs(total - 1.0) <= 0.01;

  async function save() {
    if (!withinTolerance) {
      toast.error(
        `Soma dos pesos deve ser 1.00 ± 0.01 (atual: ${total.toFixed(2)})`,
      );
      return;
    }
    setSaving(true);
    try {
      const r = await api.put<PortfolioConfig>("/portfolio/config", {
        health_score_weights: weights,
      });
      setCfg(r.data);
      setWeights({ ...DEFAULT_WEIGHTS, ...r.data.health_score_weights });
      toast.success("Pesos atualizados — Health Score recalcula em tempo real");
    } catch (e) {
      toast.error(asApiError(e).message);
    } finally {
      setSaving(false);
    }
  }

  function resetDefaults() {
    setWeights({ ...DEFAULT_WEIGHTS });
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
          <CardTitle>5 dimensões ponderadas</CardTitle>
          <CardDescription>
            Fórmula da <strong>spec v3.1 §10.3</strong>. Defaults ancorados em 35/25/20/10/10.
            Soma deve ser 1.00 ± 0.01. Mudança aqui afeta o Health Score de todos os
            projetos imediatamente.
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
                  value={weights[f.key]}
                  onChange={(e) =>
                    setWeights({
                      ...weights,
                      [f.key]: Number(e.target.value || 0),
                    })
                  }
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Normalizado</Label>
                <p className="pt-2 font-mono text-sm">{normalize(weights[f.key]).toFixed(1)}%</p>
              </div>
            </div>
          ))}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
            <div className="text-xs text-muted-foreground">
              Soma atual:{" "}
              <strong
                className={
                  withinTolerance ? "text-foreground" : "text-destructive"
                }
              >
                {total.toFixed(2)}
              </strong>{" "}
              {withinTolerance ? "(dentro da tolerância)" : "(deve ficar em 1.00 ± 0.01)"}
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={resetDefaults} disabled={saving}>
                Restaurar defaults (35/25/20/10/10)
              </Button>
              <Button onClick={save} disabled={saving || !withinTolerance}>
                {saving ? "Salvando…" : "Salvar pesos"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </AppShell>
  );
}
