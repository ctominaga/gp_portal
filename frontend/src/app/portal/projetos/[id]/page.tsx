"use client";

import { AlertTriangle, BookOpenCheck, CheckCircle2, Clock4 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { HealthGauge } from "@/components/health-gauge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, asApiError } from "@/lib/api";
import { formatDate, ragColor, ragLabel, reportStatusLabel } from "@/lib/format";
import type { ClientProjectView, HealthBand } from "@/lib/types";

function bandFromScore(score: number | null): HealthBand {
  if (score === null) return "amber";
  if (score >= 70) return "green";
  if (score >= 40) return "amber";
  return "red";
}

export default function ClientProjectPage() {
  const { id } = useParams<{ id: string }>();
  const [view, setView] = useState<ClientProjectView | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function load() {
    try {
      const r = await api.get<ClientProjectView>(`/client/projects/${id}`);
      setView(r.data);
    } catch (e) {
      toast.error(asApiError(e).message);
    }
  }

  async function confirmRead(reportId: string) {
    setConfirming(reportId);
    try {
      await api.post(`/client/reports/${reportId}/confirm-read`);
      toast.success("Leitura confirmada. Obrigado!");
      await load();
    } catch (e) {
      toast.error(asApiError(e).message);
    } finally {
      setConfirming(null);
    }
  }

  const allClientPendings = useMemo(() => {
    if (!view) return [];
    const seen = new Set<string>();
    const items: Array<{
      report_id: string;
      description: string;
      due_date: string | null;
    }> = [];
    for (const r of view.reports) {
      for (const p of r.pending_items) {
        const key = `${p.description}::${p.due_date ?? ""}`;
        if (seen.has(key)) continue;
        seen.add(key);
        items.push({
          report_id: r.id,
          description: p.description,
          due_date: p.due_date,
        });
      }
    }
    return items;
  }, [view]);

  if (!view) {
    return (
      <AppShell>
        <Skeleton className="h-96" />
      </AppShell>
    );
  }

  const score = view.health_score ?? 0;
  const band = bandFromScore(view.health_score);
  const pendingApprovalCount = view.reports.filter((r) => r.status === "pmo_approved").length;

  return (
    <AppShell>
      <div className="mb-6">
        <p className="text-sm text-muted-foreground">
          <Link href="/portal" className="hover:underline">
            ← meus projetos
          </Link>
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">{view.name}</h1>
        <p className="text-sm text-muted-foreground">{view.client_name}</p>
      </div>

      {/* Semáforo grande + sinais consolidados */}
      <Card className="mb-6">
        <CardContent className="flex flex-col items-center gap-6 py-6 sm:flex-row sm:items-center sm:gap-10">
          <HealthGauge score={score} band={band} size="lg" />
          <div className="flex-1 space-y-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs uppercase tracking-wider text-muted-foreground">
                Status atual
              </span>
              {view.latest_rag ? (
                <Badge variant={ragColor(view.latest_rag)} className="text-sm">
                  {ragLabel(view.latest_rag)}
                </Badge>
              ) : (
                <span className="text-muted-foreground">sem reports ainda</span>
              )}
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Este indicador combina avanço dos entregáveis, riscos abertos, pendências e
              prazos. Um número alto significa projeto saudável; abaixo de 40 indica situação
              crítica que demanda sua atenção.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              {pendingApprovalCount > 0 && (
                <Badge variant="red" className="gap-1">
                  <BookOpenCheck className="h-3 w-3" />
                  {pendingApprovalCount} report(s) aguardando sua leitura
                </Badge>
              )}
              {view.open_pending_items > 0 && (
                <Badge variant="amber" className="gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  {view.open_pending_items} pendência(s) com você
                </Badge>
              )}
              {view.open_risks_count > 0 && (
                <Badge variant="outline">
                  {view.open_risks_count} risco(s) abertos sendo monitorados
                </Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Pendências consolidadas do cliente */}
      {allClientPendings.length > 0 && (
        <Card className="mb-6 border-amber-200 bg-amber-50/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              Pendências aguardando você
            </CardTitle>
            <CardDescription>
              Itens que dependem da sua decisão ou aprovação para o projeto avançar.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {allClientPendings.map((p, i) => (
              <div
                key={i}
                className="flex items-start justify-between gap-3 rounded-md border border-amber-200 bg-background p-3 text-sm"
              >
                <div className="flex-1">
                  <p className="font-medium">{p.description}</p>
                  {p.due_date && (
                    <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock4 className="h-3 w-3" />
                      Prazo: {formatDate(p.due_date)}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Timeline de reports */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Reports do projeto</CardTitle>
          <CardDescription>
            Histórico em ordem reversa. Reports aprovados pelo PMO precisam da sua confirmação
            de leitura.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {view.reports.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Nenhum report liberado ainda. Você será notificado quando o primeiro for aprovado.
            </p>
          )}
          {view.reports.map((r) => {
            const needsRead = r.status === "pmo_approved";
            return (
              <div
                key={r.id}
                className={`rounded-md border p-4 ${
                  needsRead ? "border-primary/40 bg-primary/5" : ""
                }`}
              >
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <strong className="text-sm">
                    {formatDate(r.period_start)} → {formatDate(r.period_end)}
                  </strong>
                  {r.rag_status && (
                    <Badge variant={ragColor(r.rag_status)}>{ragLabel(r.rag_status)}</Badge>
                  )}
                  <Badge variant="outline">{reportStatusLabel(r.status)}</Badge>
                  {needsRead && (
                    <Badge variant="red" className="ml-auto">
                      novo — aguardando leitura
                    </Badge>
                  )}
                  {r.status === "client_released" && (
                    <Badge variant="green" className="ml-auto gap-1">
                      <CheckCircle2 className="h-3 w-3" />
                      lido
                    </Badge>
                  )}
                </div>
                {r.highlights && (
                  <div className="mb-2">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Destaques
                    </p>
                    <p className="whitespace-pre-wrap text-sm">{r.highlights}</p>
                  </div>
                )}
                {r.next_steps && (
                  <div className="mb-2">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Próximos passos
                    </p>
                    <p className="whitespace-pre-wrap text-sm">{r.next_steps}</p>
                  </div>
                )}
                {needsRead && (
                  <div className="mt-3 flex items-center gap-3 border-t pt-3">
                    <p className="flex-1 text-xs text-muted-foreground">
                      Ao confirmar leitura, o GP é notificado e o report é registrado como
                      ciente.
                    </p>
                    <Button
                      onClick={() => void confirmRead(r.id)}
                      disabled={confirming === r.id}
                      size="sm"
                    >
                      <BookOpenCheck className="mr-2 h-4 w-4" />
                      {confirming === r.id ? "Confirmando…" : "Confirmar leitura"}
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </AppShell>
  );
}
