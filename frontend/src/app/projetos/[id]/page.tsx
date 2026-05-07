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
import { formatDate } from "@/lib/format";
import type { Baseline, Project } from "@/lib/types";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [activeBaseline, setActiveBaseline] = useState<Baseline | null>(null);
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
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
