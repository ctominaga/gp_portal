"use client";

import { CheckCircle2, FileWarning, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { api, asApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Baseline, Project, ProjectRetrospective } from "@/lib/types";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [project, setProject] = useState<Project | null>(null);
  const [activeBaseline, setActiveBaseline] = useState<Baseline | null>(null);
  const [retrospective, setRetrospective] = useState<ProjectRetrospective | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    void (async () => {
      try {
        const [p, b] = await Promise.all([
          api.get<Project>(`/projects/${id}`),
          api.get<Baseline | null>(`/projects/${id}/active-baseline`),
        ]);
        setProject(p.data);
        setActiveBaseline(b.data);
        // Carrega retrospectiva apenas se projeto está fechado — evita 404
        // ruidoso pra projetos ativos.
        if (p.data.status === "closed") {
          try {
            const r = await api.get<ProjectRetrospective>(
              `/projects/${id}/retrospective`,
            );
            setRetrospective(r.data);
          } catch {
            // 404 raro (closed sem retro): seguir, banner mostra encerramento
            // mas sem detalhe.
          }
        }
      } catch (e) {
        toast.error(asApiError(e).message);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  if (loading) {
    return (
      <AppShell>
        <Skeleton className="h-32" />
      </AppShell>
    );
  }
  if (!project) {
    return (
      <AppShell>
        <Card>
          <CardHeader>
            <CardTitle>Projeto não encontrado</CardTitle>
          </CardHeader>
        </Card>
      </AppShell>
    );
  }

  const isOwnerGP =
    user?.role === "GP" && project.gp_user_id === user.id;
  const showCloseButton = isOwnerGP && project.status === "active";
  const isClosed = project.status === "closed";

  return (
    <AppShell>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">{project.client_name}</p>
          <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
        </div>
        <Badge variant={project.status === "active" ? "default" : "secondary"}>
          {project.status}
        </Badge>
      </div>

      {isClosed && (
        <Card className="mb-6 border-emerald-300 bg-emerald-50/50">
          <CardContent className="flex items-start gap-3 py-4 text-sm">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
            <p>
              <strong>Projeto encerrado{" "}
              {project.ended_at ? `em ${formatDate(project.ended_at)}` : ""}.</strong>{" "}
              A retrospectiva abaixo é o registro permanente do ciclo.
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Visão geral</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p className="whitespace-pre-wrap text-muted-foreground">
              {project.description || "Sem descrição."}
            </p>
            <p>Início: <strong>{formatDate(project.started_at)}</strong></p>
            {project.ended_at && (
              <p>Encerramento: <strong>{formatDate(project.ended_at)}</strong></p>
            )}
            <p>Cliente associado: <strong>{project.client_user_id ? "configurado" : "não configurado"}</strong></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Baseline ativo</CardTitle>
            <CardDescription>
              Escopo extraído da última proposta ativada
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {activeBaseline ? (
              <>
                <p>
                  <Badge variant="default" className="mr-2">{activeBaseline.deliverables.length}</Badge>
                  entregáveis no escopo ativo.
                </p>
                <Button asChild variant="outline">
                  <Link href={`/projetos/${project.id}/baseline/${activeBaseline.id}`}>
                    Ver baseline
                  </Link>
                </Button>
              </>
            ) : (
              <p className="text-muted-foreground">
                Nenhum baseline ativo. Faça o upload da proposta para começar.
              </p>
            )}
          </CardContent>
        </Card>

        {!isClosed && (
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>Próximos passos</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <Button asChild>
                <Link href={`/projetos/${project.id}/proposta/nova`}>Enviar proposta</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={`/projetos/${project.id}/reports/novo`}>Novo report</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={`/projetos/${project.id}/reports`}>Histórico</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={`/projetos/${project.id}/diff`}>Comparar baselines</Link>
              </Button>
              {showCloseButton && (
                <Button
                  asChild
                  variant="destructive"
                  className="ml-auto"
                  data-testid="btn-close-project"
                >
                  <Link href={`/projetos/${project.id}/encerramento`}>
                    <ShieldCheck className="mr-2 h-4 w-4" />
                    Encerrar projeto
                  </Link>
                </Button>
              )}
            </CardContent>
          </Card>
        )}

        {isClosed && retrospective && (
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>Retrospectiva</CardTitle>
              <CardDescription>
                Registro estruturado do encerramento. Alimenta o agente de
                inteligência cruzada do portfólio (v3.1 §10.4).
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-md border bg-muted/30 p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Entregue vs. Proposto
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm">
                  {retrospective.delivered_vs_proposed}
                </p>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  O que faria diferente
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm">
                  {retrospective.would_do_differently}
                </p>
              </div>
              <div className="rounded-md border bg-muted/30 p-3 sm:col-span-2">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Feedback do cliente
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm">
                  {retrospective.client_feedback}
                </p>
              </div>
              <div className="rounded-md border bg-muted/30 p-3 sm:col-span-2">
                <p className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
                  <FileWarning className="h-4 w-4" />
                  Riscos materializados ({retrospective.materialized_risks.length})
                </p>
                {retrospective.materialized_risks.length === 0 ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Nenhum risco materializou — cenário ideal.
                  </p>
                ) : (
                  <ul className="mt-2 space-y-2 text-sm">
                    {retrospective.materialized_risks.map((mr) => (
                      <li key={mr.risk_id} className="border-l-2 border-amber-300 pl-3">
                        <p className="font-mono text-xs text-muted-foreground">
                          {mr.risk_id}
                        </p>
                        {mr.comment && (
                          <p className="text-sm">{mr.comment}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <p className="sm:col-span-2 text-xs text-muted-foreground">
                Encerrado em <strong>{formatDate(retrospective.created_at)}</strong>
                {" "}por <code>{retrospective.created_by_id.slice(0, 8)}…</code>
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
