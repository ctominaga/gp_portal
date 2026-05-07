"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, asApiError } from "@/lib/api";
import { formatDate, ragColor, ragLabel, reportStatusLabel } from "@/lib/format";
import type { Project, ReportSummary } from "@/lib/types";

interface ProjectRow extends Project {
  latestReport: ReportSummary | null;
  reportCount: number;
}

export default function DashboardPage() {
  const [rows, setRows] = useState<ProjectRow[] | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const r = await api.get<Project[]>("/projects");
        const enriched: ProjectRow[] = await Promise.all(
          r.data.map(async (p) => {
            try {
              const reps = await api.get<ReportSummary[]>(`/projects/${p.id}/reports`);
              return {
                ...p,
                latestReport: reps.data[0] ?? null,
                reportCount: reps.data.length,
              };
            } catch {
              return { ...p, latestReport: null, reportCount: 0 };
            }
          }),
        );
        setRows(enriched);
      } catch (e) {
        toast.error(asApiError(e).message);
        setRows([]);
      }
    })();
  }, []);

  return (
    <AppShell>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Seus projetos e o status mais recente de cada um.
          </p>
        </div>
        <Button asChild>
          <Link href="/projetos/novo">Novo projeto</Link>
        </Button>
      </div>

      {rows === null ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-44" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Sem projetos ainda</CardTitle>
            <CardDescription>Crie um projeto para começar.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((p) => (
            <Card key={p.id} className="transition hover:shadow-md">
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardDescription>{p.client_name}</CardDescription>
                    <CardTitle className="text-base">
                      <Link href={`/projetos/${p.id}`} className="hover:underline">
                        {p.name}
                      </Link>
                    </CardTitle>
                  </div>
                  {p.latestReport?.rag_status && (
                    <Badge variant={ragColor(p.latestReport.rag_status)}>
                      {ragLabel(p.latestReport.rag_status)}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {p.latestReport ? (
                  <div className="text-muted-foreground">
                    Último report:{" "}
                    <strong>
                      {formatDate(p.latestReport.period_start)} →{" "}
                      {formatDate(p.latestReport.period_end)}
                    </strong>{" "}
                    · {reportStatusLabel(p.latestReport.status)}
                  </div>
                ) : (
                  <div className="text-muted-foreground">Nenhum report ainda.</div>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button asChild size="sm">
                    <Link href={`/projetos/${p.id}/reports/novo`}>Novo report</Link>
                  </Button>
                  <Button asChild size="sm" variant="outline">
                    <Link href={`/projetos/${p.id}/reports`}>Histórico ({p.reportCount})</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
