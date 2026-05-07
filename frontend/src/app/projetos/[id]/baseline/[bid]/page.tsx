"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, asApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { deliverableSchema, type DeliverableInput } from "@/lib/schemas";
import type { Baseline, BaselineAudit, Deliverable } from "@/lib/types";

type DialogMode = { kind: "edit"; deliverable: Deliverable } | { kind: "create" } | null;

const COMPLEXITY_TOOLTIPS: Record<string, string> = {
  low: "Baixa: rotinas pequenas, dependências mínimas, baixo risco regulatório.",
  medium: "Média: rotinas com lógica intermediária, algumas dependências entre etapas.",
  high: "Alta: alta densidade lógica, múltiplas dependências, regras regulatórias complexas.",
};

export default function BaselineReviewPage() {
  const { id: projectId, bid } = useParams<{ id: string; bid: string }>();
  const router = useRouter();
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [dialog, setDialog] = useState<DialogMode>(null);
  const [activateOpen, setActivateOpen] = useState(false);
  const [activating, setActivating] = useState(false);
  // Source excerpt EXPANDED por padrão (F3.5.1); chave = deliverable.id; valor=true => colapsado
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const refetch = useCallback(async () => {
    try {
      const r = await api.get<Baseline>(`/baselines/${bid}`);
      setBaseline(r.data);
    } catch (e) {
      toast.error(asApiError(e).message);
    }
  }, [bid]);

  useEffect(() => {
    if (bid) void refetch();
  }, [bid, refetch]);

  const groupedByPhase = useMemo(() => {
    if (!baseline) return [] as Array<{ phase: string; items: Deliverable[] }>;
    const groups = new Map<string, Deliverable[]>();
    for (const d of baseline.deliverables) {
      const k = d.phase ?? "(sem fase)";
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k)!.push(d);
    }
    return Array.from(groups.entries()).map(([phase, items]) => ({ phase, items }));
  }, [baseline]);

  async function handleDelete(deliverableId: string) {
    if (!confirm("Remover este entregável?")) return;
    try {
      await api.delete(`/deliverables/${deliverableId}`);
      toast.success("Entregável removido");
      await refetch();
    } catch (e) {
      toast.error(asApiError(e).message);
    }
  }

  async function handleActivate() {
    if (!baseline) return;
    setActivating(true);
    try {
      await api.post(`/baselines/${baseline.id}/activate`);
      toast.success("Baseline ativada");
      router.replace(`/projetos/${projectId}`);
    } catch (e) {
      toast.error(asApiError(e).message);
    } finally {
      setActivating(false);
      setActivateOpen(false);
    }
  }

  if (!baseline) {
    return (
      <AppShell>
        <Skeleton className="h-96" />
      </AppShell>
    );
  }

  const isDraft = baseline.status === "draft";
  const summary = (baseline.payload?.summary as string | undefined) ?? null;
  const phasesPayload =
    (baseline.payload?.phases as Array<{ name?: string; phase_id?: string; deliverable_count?: number }> | undefined) ??
    [];
  const audit: BaselineAudit | undefined = baseline.payload?.audit;
  const deliverableCount = baseline.deliverables.length;
  const phaseCount = groupedByPhase.length;

  return (
    <AppShell>
      <div className="mb-2 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">Revisão de baseline</p>
          <h1 className="text-2xl font-semibold tracking-tight">
            {deliverableCount} entregáveis em {phaseCount} fase{phaseCount === 1 ? "" : "s"} ·{" "}
            <Badge variant={isDraft ? "amber" : "green"}>{baseline.status}</Badge>
          </h1>
        </div>
        {isDraft && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setDialog({ kind: "create" })}>
              Adicionar entregável
            </Button>
            <Button onClick={() => setActivateOpen(true)} disabled={activating}>
              Ativar baseline
            </Button>
          </div>
        )}
      </div>

      {/* Sub-cabeçalho de auditoria (F3.5.7) */}
      {audit && (
        <div
          data-testid="baseline-audit-header"
          className="mb-6 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border bg-muted/40 px-4 py-2 text-xs text-muted-foreground"
        >
          <span>
            Extraído de{" "}
            <Link
              href={`/projetos/${projectId}/proposta/${baseline.proposal_id}`}
              className="font-medium text-foreground underline-offset-2 hover:underline"
            >
              {audit.source_proposal_filename ?? "proposta"}
              {audit.source_proposal_version ? ` v${audit.source_proposal_version}` : null}
            </Link>
          </span>
          {audit.extracted_at && <span>· em {formatDate(audit.extracted_at)}</span>}
          {audit.engine && audit.route && (
            <span>
              · via <strong className="text-foreground">{audit.engine}</strong>/
              <strong className="text-foreground">{audit.route}</strong>
            </span>
          )}
          {typeof audit.confidence_score === "number" && (
            <span className="flex items-center gap-1.5">
              · confiança{" "}
              <strong className="text-foreground">
                {Math.round(audit.confidence_score * 100)}%
              </strong>
              {audit.confidence_score < 0.7 && (
                <Badge
                  variant="amber"
                  className="text-[10px]"
                  title="Confiança abaixo de 70% — revise os entregáveis cuidadosamente antes de ativar."
                >
                  ⚠ baixa
                </Badge>
              )}
            </span>
          )}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          {groupedByPhase.length === 0 && (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                Nenhum entregável extraído. Adicione manualmente.
              </CardContent>
            </Card>
          )}
          {groupedByPhase.map((g) => (
            <section key={g.phase} className="space-y-3">
              <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                {g.phase}
              </h2>
              <div className="space-y-3">
                {g.items.map((d) => {
                  const isCollapsed = collapsed[d.id] === true;
                  return (
                    <Card key={d.id} className="transition hover:shadow-sm">
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <CardTitle className="text-base">
                              {d.code && <span className="text-muted-foreground">{d.code} · </span>}
                              {d.title}
                            </CardTitle>
                            {d.description && (
                              <CardDescription className="mt-1">{d.description}</CardDescription>
                            )}
                          </div>
                          <div className="flex shrink-0 gap-2">
                            {d.complexity && (
                              <Badge
                                title={COMPLEXITY_TOOLTIPS[d.complexity]}
                                variant={
                                  d.complexity === "high"
                                    ? "red"
                                    : d.complexity === "medium"
                                      ? "amber"
                                      : "green"
                                }
                              >
                                {d.complexity}
                              </Badge>
                            )}
                            {isDraft && (
                              <>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => setDialog({ kind: "edit", deliverable: d })}
                                >
                                  editar
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => void handleDelete(d.id)}
                                >
                                  remover
                                </Button>
                              </>
                            )}
                          </div>
                        </div>
                      </CardHeader>
                      {d.source_excerpt && (
                        <CardContent className="pt-0">
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-medium uppercase tracking-wide text-amber-700">
                              Trecho da proposta original
                            </p>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs"
                              onClick={() =>
                                setCollapsed((c) => ({ ...c, [d.id]: !isCollapsed }))
                              }
                              aria-label={isCollapsed ? "expandir" : "colapsar"}
                            >
                              {isCollapsed ? "expandir" : "colapsar"}
                            </Button>
                          </div>
                          {!isCollapsed && (
                            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded border-l-4 border-amber-400 bg-amber-50 p-3 font-mono text-xs leading-relaxed text-amber-900">
{d.source_excerpt}
                            </pre>
                          )}
                        </CardContent>
                      )}
                    </Card>
                  );
                })}
              </div>
            </section>
          ))}
        </div>

        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Resumo da extração</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              {summary ? <p>{summary}</p> : <p>Sem resumo gerado.</p>}
              <p className="pt-2 text-xs">
                <strong className="text-foreground">{deliverableCount}</strong> entregáveis em{" "}
                <strong className="text-foreground">{phaseCount}</strong> fase
                {phaseCount === 1 ? "" : "s"}.
              </p>
              {phasesPayload.length > 0 && (
                <ul className="space-y-1 pt-2">
                  {phasesPayload.map((p, i) => (
                    <li key={i} className="text-xs">
                      <strong>{p.name ?? p.phase_id}</strong>
                      {typeof p.deliverable_count === "number" ? (
                        <span> ({p.deliverable_count})</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Atalhos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Button asChild variant="ghost" className="w-full justify-start">
                <Link href={`/projetos/${projectId}`}>← Voltar ao projeto</Link>
              </Button>
              <Button asChild variant="ghost" className="w-full justify-start">
                <Link href={`/projetos/${projectId}/proposta/${baseline.proposal_id}`}>
                  Ver proposta original
                </Link>
              </Button>
            </CardContent>
          </Card>
        </aside>
      </div>

      {dialog && (
        <DeliverableDialog
          mode={dialog}
          baselineId={baseline.id}
          onClose={() => setDialog(null)}
          onSaved={async () => {
            setDialog(null);
            await refetch();
          }}
        />
      )}

      {/* Modal de ativação (F3.5.2) */}
      <Dialog open={activateOpen} onOpenChange={(o) => !activating && setActivateOpen(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ativar baseline?</DialogTitle>
            <DialogDescription className="pt-2">
              Você está aceitando <strong className="text-foreground">{deliverableCount}</strong>{" "}
              entregáveis em <strong className="text-foreground">{phaseCount}</strong> fase
              {phaseCount === 1 ? "" : "s"} como contrato deste projeto. Após ativação, mudanças
              exigirão upload de proposta v2.
              <span className="mt-2 block font-medium text-destructive">
                Esta ação não pode ser desfeita.
              </span>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setActivateOpen(false)} disabled={activating}>
              Cancelar
            </Button>
            <Button onClick={handleActivate} disabled={activating}>
              {activating ? "Ativando…" : "Sim, ativar baseline"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}

function DeliverableDialog({
  mode,
  baselineId,
  onClose,
  onSaved,
}: {
  mode: { kind: "edit"; deliverable: Deliverable } | { kind: "create" };
  baselineId: string;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const isEdit = mode.kind === "edit";
  const initial = isEdit
    ? {
        code: mode.deliverable.code ?? "",
        title: mode.deliverable.title,
        description: mode.deliverable.description ?? "",
        phase: mode.deliverable.phase ?? "",
        category: mode.deliverable.category ?? "",
        complexity: (mode.deliverable.complexity ?? undefined) as "low" | "medium" | "high" | undefined,
        source_excerpt: mode.deliverable.source_excerpt ?? "",
        due_date: mode.deliverable.due_date ?? "",
      }
    : { title: "" };

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<DeliverableInput>({
    resolver: zodResolver(deliverableSchema),
    defaultValues: initial,
  });

  async function onSubmit(values: DeliverableInput) {
    const payload: Record<string, unknown> = {};
    Object.entries(values).forEach(([k, v]) => {
      if (v !== "" && v !== undefined && v !== null) payload[k] = v;
    });
    try {
      if (isEdit) {
        await api.patch(`/deliverables/${mode.deliverable.id}`, payload);
        toast.success("Entregável atualizado");
      } else {
        await api.post(`/baselines/${baselineId}/deliverables`, payload);
        toast.success("Entregável criado");
      }
      await onSaved();
    } catch (e) {
      toast.error(asApiError(e).message);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => (!o ? onClose() : null)}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Editar entregável" : "Novo entregável"}</DialogTitle>
          <DialogDescription>
            Os campos código, fase e complexidade ajudam o report depois.
          </DialogDescription>
        </DialogHeader>
        <form id="deliv-form" onSubmit={handleSubmit(onSubmit)} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-[120px_1fr]">
            <div className="space-y-1">
              <Label>Código</Label>
              <Input placeholder="d-001" {...register("code")} />
            </div>
            <div className="space-y-1">
              <Label>Título *</Label>
              <Input {...register("title")} />
              {errors.title && <p className="text-xs text-destructive">{errors.title.message}</p>}
            </div>
          </div>
          <div className="space-y-1">
            <Label>Descrição</Label>
            <Textarea rows={2} {...register("description")} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <Label>Fase</Label>
              <Input placeholder="sprint-1" {...register("phase")} />
            </div>
            <div className="space-y-1">
              <Label>Categoria</Label>
              <Input {...register("category")} />
            </div>
            <div className="space-y-1">
              <Label>Complexidade</Label>
              <Select
                value={watch("complexity") ?? ""}
                onValueChange={(v) =>
                  setValue("complexity", v as "low" | "medium" | "high", { shouldDirty: true })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">low</SelectItem>
                  <SelectItem value="medium">medium</SelectItem>
                  <SelectItem value="high">high</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Trecho da proposta (source excerpt)</Label>
            <Textarea
              rows={3}
              className="font-mono text-xs"
              placeholder="Cole aqui o trecho literal da proposta que originou este entregável."
              {...register("source_excerpt")}
            />
          </div>
          <div className="space-y-1">
            <Label>Prazo</Label>
            <Input type="date" {...register("due_date")} />
          </div>
        </form>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" form="deliv-form" disabled={isSubmitting}>
            {isSubmitting ? "Salvando…" : isEdit ? "Salvar" : "Criar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
