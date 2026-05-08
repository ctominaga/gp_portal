"use client";

import { AlertTriangle, FileCheck2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { HealthGauge } from "@/components/health-gauge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, asApiError } from "@/lib/api";
import { ragColor, ragLabel } from "@/lib/format";
import type { ClientProjectView, HealthBand } from "@/lib/types";

function bandFromScore(score: number | null): HealthBand {
  if (score === null) return "amber";
  if (score >= 70) return "green";
  if (score >= 40) return "amber";
  return "red";
}

export default function ClientPortalPage() {
  const [projects, setProjects] = useState<ClientProjectView[] | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const r = await api.get<ClientProjectView[]>("/client/projects");
        setProjects(r.data);
      } catch (e) {
        toast.error(asApiError(e).message);
      }
    })();
  }, []);

  if (!projects) {
    return (
      <AppShell>
        <Skeleton className="h-96" />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mb-6">
        <p className="text-sm text-muted-foreground">Portal do cliente</p>
        <h1 className="text-2xl font-semibold tracking-tight">Meus projetos</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Aqui você acompanha o status dos projetos contratados, lê os reports liberados pela
          Jump Label e confirma sua leitura.
        </p>
      </div>

      {projects.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            Você ainda não tem projetos atribuídos. Aguarde liberação pelo PMO.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((p) => {
            const score = p.health_score ?? 0;
            const band = bandFromScore(p.health_score);
            const unreadCount = p.reports.filter(
              (r) => r.status === "pmo_approved",
            ).length;
            return (
              <Card key={p.id} className="transition hover:shadow-md">
                <CardHeader className="pb-3">
                  <CardDescription>{p.client_name}</CardDescription>
                  <CardTitle className="text-base">
                    <Link href={`/portal/projetos/${p.id}`} className="hover:underline">
                      {p.name}
                    </Link>
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex items-center gap-4">
                  <HealthGauge score={score} band={band} size="md" />
                  <div className="flex-1 space-y-2 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">Último status</span>
                      {p.latest_rag ? (
                        <Badge variant={ragColor(p.latest_rag)}>{ragLabel(p.latest_rag)}</Badge>
                      ) : (
                        <span className="text-xs">—</span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1.5 text-xs">
                      {p.open_pending_items > 0 && (
                        <Badge variant="amber" className="gap-1">
                          <AlertTriangle className="h-3 w-3" />
                          {p.open_pending_items} pendência(s) sua(s)
                        </Badge>
                      )}
                      {unreadCount > 0 && (
                        <Badge variant="red" className="gap-1">
                          <FileCheck2 className="h-3 w-3" />
                          {unreadCount} report(s) para ler
                        </Badge>
                      )}
                      {p.open_risks_count > 0 && (
                        <Badge variant="outline">{p.open_risks_count} risco(s) acompanhados</Badge>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
