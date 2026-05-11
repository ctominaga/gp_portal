"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { HealthGauge } from "@/components/health-gauge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, asApiError } from "@/lib/api";
import { ragColor, ragLabel } from "@/lib/format";
import type { PortfolioOverview } from "@/lib/types";

export default function PortfolioPage() {
  const [overview, setOverview] = useState<PortfolioOverview | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const r = await api.get<PortfolioOverview>("/portfolio");
        setOverview(r.data);
      } catch (e) {
        toast.error(asApiError(e).message);
      }
    })();
  }, []);

  if (!overview) {
    return (
      <AppShell>
        <Skeleton className="h-96" />
      </AppShell>
    );
  }

  const totalCritical = overview.projects.reduce((s, p) => s + p.open_critical_alerts, 0);

  return (
    <AppShell>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">PMO</p>
          <h1 className="text-2xl font-semibold tracking-tight">Portfólio</h1>
        </div>
        <Button asChild variant="outline">
          <Link href="/pmo/portfolio/config">Configurar pesos do Health Score</Link>
        </Button>
      </div>

      {/* Sumário consolidado (padrão F3.5: agregado computado visível) */}
      <div className="mb-6 grid gap-4 sm:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Projetos</CardDescription>
            <CardTitle className="text-3xl">{overview.total_projects}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Health médio</CardDescription>
            <CardTitle className="text-3xl">
              {overview.avg_health_score !== null ? overview.avg_health_score.toFixed(0) : "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Distribuição</CardDescription>
            <CardTitle className="flex flex-wrap gap-1 text-base">
              <Badge variant="green">{overview.counts_by_band.green} verde</Badge>
              <Badge variant="amber">{overview.counts_by_band.amber} âmbar</Badge>
              <Badge variant="red">{overview.counts_by_band.red} vermelho</Badge>
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className={totalCritical > 0 ? "border-destructive" : ""}>
          <CardHeader className="pb-2">
            <CardDescription>Alertas críticos abertos</CardDescription>
            <CardTitle className="flex items-center gap-2 text-3xl">
              {totalCritical > 0 && <AlertTriangle className="h-7 w-7 text-destructive" />}
              {totalCritical}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {overview.projects.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            Nenhum projeto cadastrado.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {overview.projects.map((p) => (
            <Card
              key={p.project_id}
              className="transition hover:shadow-md"
              data-testid={`portfolio-card-${p.project_id}`}
            >
              <CardHeader className="pb-3">
                <CardDescription>{p.client_name}</CardDescription>
                <CardTitle className="text-base">
                  <Link href={`/projetos/${p.project_id}`} className="hover:underline">
                    {p.project_name}
                  </Link>
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  GP: {p.gp_name ?? "—"}
                </p>
              </CardHeader>
              <CardContent className="flex items-center gap-4">
                <div
                  title={
                    `Health Score = ${p.health.score} (${p.health.band})\n` +
                    `RAG médio: ${p.health.components.rag_avg.toFixed(1)}\n` +
                    `SPI: ${p.health.components.spi.toFixed(1)}\n` +
                    `Risco inverso: ${p.health.components.risk_inverse.toFixed(1)}\n` +
                    `Resolução: ${p.health.components.resolution_rate.toFixed(1)}\n` +
                    `Estabilidade: ${p.health.components.stability.toFixed(1)}`
                  }
                >
                  <HealthGauge score={p.health.score} band={p.health.band} size="md" />
                </div>
                <div className="flex-1 space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Último RAG</span>
                    {p.last_report_rag ? (
                      <Badge variant={ragColor(p.last_report_rag)}>
                        {ragLabel(p.last_report_rag)}
                      </Badge>
                    ) : (
                      <span className="text-xs">—</span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5 text-xs">
                    <Badge variant="secondary">{p.open_risks_count} risco(s)</Badge>
                    {p.open_critical_alerts > 0 && (
                      <Badge variant="red" className="gap-1">
                        <AlertTriangle className="h-3 w-3" /> {p.open_critical_alerts} crítico(s)
                      </Badge>
                    )}
                    <Badge variant="outline">{p.pending_client_items} pendência(s) cliente</Badge>
                  </div>
                  {/* 5 componentes do Health Score (spec v3.1 §10.3) */}
                  <div className="space-y-0.5 pt-1 text-xs text-muted-foreground">
                    <p>
                      RAG{" "}
                      <strong className="text-foreground">{p.health.components.rag_avg.toFixed(0)}</strong>{" "}
                      · SPI{" "}
                      <strong className="text-foreground">{p.health.components.spi.toFixed(0)}</strong>{" "}
                      · Risco⁻¹{" "}
                      <strong className="text-foreground">{p.health.components.risk_inverse.toFixed(0)}</strong>{" "}
                      · Resol.{" "}
                      <strong className="text-foreground">{p.health.components.resolution_rate.toFixed(0)}</strong>{" "}
                      · Estab.{" "}
                      <strong className="text-foreground">{p.health.components.stability.toFixed(0)}</strong>
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
