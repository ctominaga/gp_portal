"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, asApiError } from "@/lib/api";
import { formatDate, ragColor, ragLabel, reportStatusLabel } from "@/lib/format";
import type { ReportSummary } from "@/lib/types";

export default function ReportsHistoryPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const [reports, setReports] = useState<ReportSummary[] | null>(null);

  useEffect(() => {
    if (!projectId) return;
    void (async () => {
      try {
        const r = await api.get<ReportSummary[]>(`/projects/${projectId}/reports`);
        setReports(r.data);
      } catch (e) {
        toast.error(asApiError(e).message);
        setReports([]);
      }
    })();
  }, [projectId]);

  return (
    <AppShell>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Reports do projeto</p>
          <h1 className="text-2xl font-semibold tracking-tight">Histórico</h1>
        </div>
        <Button asChild>
          <Link href={`/projetos/${projectId}/reports/novo`}>Novo report</Link>
        </Button>
      </div>

      {reports === null ? (
        <Skeleton className="h-40" />
      ) : reports.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Nenhum report</CardTitle>
            <CardDescription>Crie o primeiro para começar o histórico.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Período</th>
                  <th className="px-4 py-3">RAG</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Criado em</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <strong>{formatDate(r.period_start)}</strong> → {formatDate(r.period_end)}
                    </td>
                    <td className="px-4 py-3">
                      {r.rag_status ? (
                        <Badge variant={ragColor(r.rag_status)}>{ragLabel(r.rag_status)}</Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">{reportStatusLabel(r.status)}</td>
                    <td className="px-4 py-3 text-muted-foreground">{formatDate(r.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link href={`/projetos/${projectId}/reports/${r.id}/edit`}>abrir</Link>
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </AppShell>
  );
}
