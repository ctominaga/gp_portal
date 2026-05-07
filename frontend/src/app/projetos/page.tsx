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
import { formatDate } from "@/lib/format";
import type { Project } from "@/lib/types";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const r = await api.get<Project[]>("/projects");
        setProjects(r.data);
      } catch (e) {
        toast.error(asApiError(e).message);
        setProjects([]);
      }
    })();
  }, []);

  return (
    <AppShell>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projetos</h1>
          <p className="text-sm text-muted-foreground">Lista dos projetos sob sua responsabilidade.</p>
        </div>
        <Button asChild>
          <Link href="/projetos/novo">Novo projeto</Link>
        </Button>
      </div>

      {projects === null ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Nenhum projeto</CardTitle>
            <CardDescription>Comece criando seu primeiro projeto.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((p) => (
            <Card key={p.id} className="transition hover:shadow-md">
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-2 text-lg">
                  <span className="line-clamp-1">{p.name}</span>
                  <Badge variant={p.status === "active" ? "default" : "secondary"}>{p.status}</Badge>
                </CardTitle>
                <CardDescription>{p.client_name}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <p className="line-clamp-2 min-h-[2.5rem]">
                  {p.description || "Sem descrição."}
                </p>
                <div className="flex items-center justify-between">
                  <span>Início: {formatDate(p.started_at)}</span>
                  <Button variant="link" size="sm" asChild>
                    <Link href={`/projetos/${p.id}`}>abrir →</Link>
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
