"use client";

import { ArrowRight, ClipboardList, MinusCircle, PencilLine, PlusCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, asApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Project, ScopeChange, ScopeChangeStatus } from "@/lib/types";

/** Agrupamento por transição: (project_id, baseline_to_id) é a unidade que
 * o PMO revisa. 1 linha da tabela = 1 batch de ScopeChanges. */
interface TransitionRow {
  project_id: string;
  baseline_to_id: string;
  baseline_from_id: string | null;
  scope_changes: ScopeChange[];
  /** Mais antigo do batch — usado para mostrar a idade da transição. */
  oldest_requested_at: string;
  has_added: boolean;
  has_removed: boolean;
  has_modified: boolean;
}

const STATUS_OPTIONS: { value: ScopeChangeStatus | "all"; label: string }[] = [
  { value: "proposed", label: "Pendentes (PROPOSED)" },
  { value: "implemented", label: "Aprovadas (IMPLEMENTED)" },
  { value: "rejected", label: "Rejeitadas (REJECTED)" },
];

function daysBetween(iso: string): number {
  const ms = Date.now() - new Date(iso).getTime();
  return Math.max(0, Math.floor(ms / (1000 * 60 * 60 * 24)));
}

function groupTransitions(rows: ScopeChange[]): TransitionRow[] {
  const map = new Map<string, TransitionRow>();
  for (const sc of rows) {
    if (!sc.baseline_to_id) continue;
    const key = `${sc.project_id}::${sc.baseline_to_id}`;
    const existing = map.get(key);
    if (existing) {
      existing.scope_changes.push(sc);
      if (sc.requested_at < existing.oldest_requested_at) {
        existing.oldest_requested_at = sc.requested_at;
      }
      if (sc.change_type === "added") existing.has_added = true;
      if (sc.change_type === "removed") existing.has_removed = true;
      if (sc.change_type === "modified") existing.has_modified = true;
    } else {
      map.set(key, {
        project_id: sc.project_id,
        baseline_to_id: sc.baseline_to_id,
        baseline_from_id: sc.baseline_from_id,
        scope_changes: [sc],
        oldest_requested_at: sc.requested_at,
        has_added: sc.change_type === "added",
        has_removed: sc.change_type === "removed",
        has_modified: sc.change_type === "modified",
      });
    }
  }
  return Array.from(map.values()).sort((a, b) =>
    a.oldest_requested_at < b.oldest_requested_at ? 1 : -1,
  );
}

export default function PmoScopeChangesPage() {
  const [rows, setRows] = useState<ScopeChange[] | null>(null);
  const [projects, setProjects] = useState<Record<string, Project>>({});
  const [statusFilter, setStatusFilter] = useState<ScopeChangeStatus | "all">("proposed");
  const [projectFilter, setProjectFilter] = useState<string>("all");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await api.get<ScopeChange[]>(
          `/scope-changes?status=${statusFilter === "all" ? "proposed" : statusFilter}`,
        );
        if (!cancelled) setRows(r.data);
      } catch (e) {
        toast.error(asApiError(e).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [statusFilter]);

  // Hidrata mapa de projetos para mostrar nome em cada linha (1 call, cached).
  useEffect(() => {
    void (async () => {
      try {
        const r = await api.get<Project[]>("/projects");
        const byId: Record<string, Project> = {};
        for (const p of r.data) byId[p.id] = p;
        setProjects(byId);
      } catch {
        // não-fatal: tabela ainda renderiza só com IDs
      }
    })();
  }, []);

  const transitions = useMemo(() => {
    if (!rows) return [];
    const all = groupTransitions(rows);
    if (projectFilter === "all") return all;
    return all.filter((t) => t.project_id === projectFilter);
  }, [rows, projectFilter]);

  const projectOptions = useMemo(() => {
    if (!rows) return [];
    const ids = new Set(rows.map((r) => r.project_id));
    return Array.from(ids).map((id) => ({
      id,
      label: projects[id]?.name ?? id.slice(0, 8),
    }));
  }, [rows, projects]);

  if (!rows) {
    return (
      <AppShell>
        <Skeleton className="h-96" />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mb-6">
        <p className="text-sm text-muted-foreground">PMO</p>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <ClipboardList className="h-6 w-6" />
          Transições de baseline pendentes
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Cada linha representa uma transição (v(N) → v(N+1)) que aguarda decisão
          do PMO. Clique em <strong>Revisar</strong> para abrir o diff e
          aprovar/rejeitar.
        </p>
      </div>

      <Card className="mb-4">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filtros</CardTitle>
          <CardDescription>
            Use os filtros para restringir o que aparece na tabela abaixo.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              Status
            </label>
            <Select
              value={statusFilter}
              onValueChange={(v) => setStatusFilter(v as ScopeChangeStatus | "all")}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              Projeto
            </label>
            <Select value={projectFilter} onValueChange={setProjectFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os projetos</SelectItem>
                {projectOptions.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {transitions.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Nenhuma transição encontrada para os filtros atuais.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-left">Projeto</th>
                  <th className="px-4 py-3 text-left">Mudanças</th>
                  <th className="px-4 py-3 text-left">Detalhe</th>
                  <th className="px-4 py-3 text-left">Idade</th>
                  <th className="px-4 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody>
                {transitions.map((t) => {
                  const projectName =
                    projects[t.project_id]?.name ?? t.project_id.slice(0, 8);
                  const days = daysBetween(t.oldest_requested_at);
                  return (
                    <tr
                      key={`${t.project_id}-${t.baseline_to_id}`}
                      className="border-b last:border-0 hover:bg-muted/20"
                      data-testid={`transition-row-${t.baseline_to_id}`}
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={`/projetos/${t.project_id}`}
                          className="font-medium hover:underline"
                        >
                          {projectName}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="secondary">
                          {t.scope_changes.length} item(ns)
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {t.has_added && (
                            <Badge variant="green" className="gap-1">
                              <PlusCircle className="h-3 w-3" />
                              add
                            </Badge>
                          )}
                          {t.has_removed && (
                            <Badge variant="red" className="gap-1">
                              <MinusCircle className="h-3 w-3" />
                              rem
                            </Badge>
                          )}
                          {t.has_modified && (
                            <Badge variant="amber" className="gap-1">
                              <PencilLine className="h-3 w-3" />
                              mod
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {days === 0
                          ? "hoje"
                          : days === 1
                            ? "ontem"
                            : `${days} dias atrás`}{" "}
                        <span className="text-xs">
                          ({formatDate(t.oldest_requested_at)})
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button asChild size="sm" variant="outline">
                          <Link
                            href={`/projetos/${t.project_id}/diff?new=${t.baseline_to_id}${
                              t.baseline_from_id ? `&base=${t.baseline_from_id}` : ""
                            }`}
                          >
                            Revisar <ArrowRight className="ml-1 h-3.5 w-3.5" />
                          </Link>
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </AppShell>
  );
}
