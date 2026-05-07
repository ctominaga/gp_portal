"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, asApiError } from "@/lib/api";
import { useAutosave, type AutosaveStatus } from "@/lib/hooks/use-autosave";
import type {
  ActionPlan,
  Baseline,
  Deliverable,
  DeliveryProgress,
  PendingItem,
  RAGStatus,
  Report,
  Risk,
} from "@/lib/types";

interface DraftState {
  period_start: string;
  period_end: string;
  rag_status: RAGStatus | null;
  highlights: string;
  next_steps: string;
  notes: string;
  progresses: DeliveryProgress[];
  risks: Risk[];
  action_plans: ActionPlan[];
  pending_items: PendingItem[];
}

function reportToDraft(r: Report): DraftState {
  return {
    period_start: r.period_start,
    period_end: r.period_end,
    rag_status: r.rag_status,
    highlights: r.highlights ?? "",
    next_steps: r.next_steps ?? "",
    notes: r.notes ?? "",
    progresses: r.progresses ?? [],
    risks: r.risks ?? [],
    action_plans: r.action_plans ?? [],
    pending_items: r.pending_items ?? [],
  };
}

export default function ReportEditPage() {
  const { id: projectId, rid } = useParams<{ id: string; rid: string }>();
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [activeBaseline, setActiveBaseline] = useState<Baseline | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Carrega report + baseline ativo
  useEffect(() => {
    if (!rid || !projectId) return;
    void (async () => {
      try {
        const [rep, ab] = await Promise.all([
          api.get<Report>(`/reports/${rid}`),
          api.get<Baseline | null>(`/projects/${projectId}/active-baseline`),
        ]);
        setReport(rep.data);
        setDraft(reportToDraft(rep.data));
        setActiveBaseline(ab.data);
      } catch (e) {
        toast.error(asApiError(e).message);
      }
    })();
  }, [rid, projectId]);

  // Pré-popula progresses com deliverables do baseline ativo (uma vez)
  useEffect(() => {
    if (!draft || !activeBaseline) return;
    if (draft.progresses.length > 0) return;
    const seeded: DeliveryProgress[] = activeBaseline.deliverables.map((d) => ({
      deliverable_id: d.id,
      status: "planned",
      percent_complete: 0,
      comment: null,
    }));
    setDraft({ ...draft, progresses: seeded });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBaseline]);

  const save = useCallback(
    async (d: DraftState) => {
      const payload: Record<string, unknown> = {
        period_start: d.period_start,
        period_end: d.period_end,
        rag_status: d.rag_status,
        highlights: d.highlights || null,
        next_steps: d.next_steps || null,
        notes: d.notes || null,
        progresses: d.progresses.map((p) => ({
          deliverable_id: p.deliverable_id,
          status: p.status,
          percent_complete: p.percent_complete,
          comment: p.comment,
        })),
        risks: d.risks.map((r) => ({
          description: r.description,
          severity: r.severity,
          owner_id: r.owner_id,
          due_date: r.due_date,
          status: r.status,
        })),
        action_plans: d.action_plans.map((a) => ({
          description: a.description,
          owner_id: a.owner_id,
          due_date: a.due_date,
          status: a.status,
        })),
        pending_items: d.pending_items.map((p) => ({
          description: p.description,
          owner_party: p.owner_party,
          due_date: p.due_date,
          status: p.status,
        })),
      };
      await api.patch(`/reports/${rid}`, payload);
    },
    [rid],
  );

  const { status: saveStatus, lastSavedAt } = useAutosave(
    draft as DraftState,
    async (v) => save(v),
    { enabled: draft !== null, debounceMs: 800 },
  );

  const deliverableById = useMemo(() => {
    const m = new Map<string, Deliverable>();
    activeBaseline?.deliverables.forEach((d) => m.set(d.id, d));
    return m;
  }, [activeBaseline]);

  async function handleSubmitFinal() {
    if (!draft || !rid) return;
    if (!draft.rag_status) {
      toast.error("Selecione o status RAG antes de submeter.");
      return;
    }
    setSubmitting(true);
    try {
      await save(draft); // garante último estado
      await api.post(`/reports/${rid}/submit`);
      toast.success("Report submetido");
      router.replace(`/projetos/${projectId}/reports`);
    } catch (e) {
      toast.error(asApiError(e).message);
      setSubmitting(false);
    }
  }

  if (!report || !draft) {
    return (
      <AppShell>
        <p className="text-sm text-muted-foreground">Carregando…</p>
      </AppShell>
    );
  }

  const isReadonly = report.status !== "draft" && report.status !== "needs_revision";

  return (
    <AppShell>
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">Wizard de report</p>
          <h1 className="text-2xl font-semibold tracking-tight">
            {draft.period_start} → {draft.period_end}{" "}
            <Badge variant="secondary" className="ml-2">{report.status}</Badge>
          </h1>
        </div>
        <SaveStatusBadge status={saveStatus} lastSavedAt={lastSavedAt} />
      </div>

      <Tabs defaultValue="ident">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="ident">1. Identificação</TabsTrigger>
          <TabsTrigger value="rag">2. RAG</TabsTrigger>
          <TabsTrigger value="prog">3. Progresso ({draft.progresses.length})</TabsTrigger>
          <TabsTrigger value="risks">4. Riscos ({draft.risks.length})</TabsTrigger>
          <TabsTrigger value="actions">5. Planos ({draft.action_plans.length})</TabsTrigger>
          <TabsTrigger value="pending">6. Pendências ({draft.pending_items.length})</TabsTrigger>
          <TabsTrigger value="hl">7. Destaques + Próximos</TabsTrigger>
        </TabsList>

        <TabsContent value="ident">
          <Card>
            <CardHeader>
              <CardTitle>Período</CardTitle>
              <CardDescription>Datas de início e fim do report.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label>Início</Label>
                <Input
                  type="date"
                  value={draft.period_start}
                  onChange={(e) => setDraft({ ...draft, period_start: e.target.value })}
                  disabled={isReadonly}
                />
              </div>
              <div className="space-y-1">
                <Label>Fim</Label>
                <Input
                  type="date"
                  value={draft.period_end}
                  onChange={(e) => setDraft({ ...draft, period_end: e.target.value })}
                  disabled={isReadonly}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rag">
          <Card>
            <CardHeader>
              <CardTitle>Status RAG</CardTitle>
              <CardDescription>Como está o projeto neste período.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-3">
                {(["G", "A", "R"] as RAGStatus[]).map((s) => (
                  <Button
                    key={s}
                    type="button"
                    variant={draft.rag_status === s ? "default" : "outline"}
                    onClick={() => setDraft({ ...draft, rag_status: s })}
                    disabled={isReadonly}
                  >
                    {s === "G" ? "Verde" : s === "A" ? "Amarelo" : "Vermelho"}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="prog">
          <Card>
            <CardHeader>
              <CardTitle>Progresso das entregas</CardTitle>
              <CardDescription>
                Pré-populado com os deliverables da baseline ativa.
                {!activeBaseline && " (nenhuma baseline ativa encontrada)"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {draft.progresses.length === 0 && (
                <p className="text-sm text-muted-foreground">Sem entregáveis ainda.</p>
              )}
              {draft.progresses.map((p, i) => {
                const d = deliverableById.get(p.deliverable_id);
                return (
                  <div
                    key={p.deliverable_id}
                    className="grid gap-3 rounded-md border p-3 sm:grid-cols-[1fr_120px_140px_140px]"
                  >
                    <div>
                      <p className="text-sm font-medium">
                        {d?.code ? `${d.code} · ` : ""}
                        {d?.title ?? p.deliverable_id}
                      </p>
                      {d?.phase && (
                        <p className="text-xs text-muted-foreground">{d.phase}</p>
                      )}
                    </div>
                    <Select
                      value={p.status}
                      onValueChange={(v) => {
                        const next = [...draft.progresses];
                        next[i] = { ...p, status: v as DeliveryProgress["status"] };
                        setDraft({ ...draft, progresses: next });
                      }}
                      disabled={isReadonly}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="planned">Planejado</SelectItem>
                        <SelectItem value="in_progress">Em andamento</SelectItem>
                        <SelectItem value="done">Concluído</SelectItem>
                        <SelectItem value="blocked">Bloqueado</SelectItem>
                      </SelectContent>
                    </Select>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      value={p.percent_complete}
                      onChange={(e) => {
                        const next = [...draft.progresses];
                        next[i] = { ...p, percent_complete: Number(e.target.value || 0) };
                        setDraft({ ...draft, progresses: next });
                      }}
                      disabled={isReadonly}
                    />
                    <Input
                      placeholder="comentário"
                      value={p.comment ?? ""}
                      onChange={(e) => {
                        const next = [...draft.progresses];
                        next[i] = { ...p, comment: e.target.value };
                        setDraft({ ...draft, progresses: next });
                      }}
                      disabled={isReadonly}
                    />
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="risks">
          <ListEditor<Risk>
            title="Riscos"
            items={draft.risks}
            empty={{ description: "", severity: "medium", owner_id: null, due_date: null, status: "open" }}
            onChange={(risks) => setDraft({ ...draft, risks })}
            disabled={isReadonly}
            renderItem={(r, set) => (
              <div className="grid gap-2 sm:grid-cols-[1fr_140px_120px]">
                <Textarea
                  rows={2}
                  placeholder="descrição"
                  value={r.description}
                  onChange={(e) => set({ ...r, description: e.target.value })}
                />
                <Select value={r.severity} onValueChange={(v) => set({ ...r, severity: v as Risk["severity"] })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">low</SelectItem>
                    <SelectItem value="medium">medium</SelectItem>
                    <SelectItem value="high">high</SelectItem>
                    <SelectItem value="critical">critical</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  type="date"
                  value={r.due_date ?? ""}
                  onChange={(e) => set({ ...r, due_date: e.target.value || null })}
                />
              </div>
            )}
          />
        </TabsContent>

        <TabsContent value="actions">
          <ListEditor<ActionPlan>
            title="Planos de ação"
            items={draft.action_plans}
            empty={{ description: "", owner_id: null, due_date: null, status: "open" }}
            onChange={(action_plans) => setDraft({ ...draft, action_plans })}
            disabled={isReadonly}
            renderItem={(a, set) => (
              <div className="grid gap-2 sm:grid-cols-[1fr_140px_120px]">
                <Textarea
                  rows={2}
                  placeholder="descrição"
                  value={a.description}
                  onChange={(e) => set({ ...a, description: e.target.value })}
                />
                <Select value={a.status} onValueChange={(v) => set({ ...a, status: v as ActionPlan["status"] })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="open">open</SelectItem>
                    <SelectItem value="in_progress">in_progress</SelectItem>
                    <SelectItem value="done">done</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  type="date"
                  value={a.due_date ?? ""}
                  onChange={(e) => set({ ...a, due_date: e.target.value || null })}
                />
              </div>
            )}
          />
        </TabsContent>

        <TabsContent value="pending">
          <ListEditor<PendingItem>
            title="Itens pendentes (do cliente ou terceiros)"
            items={draft.pending_items}
            empty={{ description: "", owner_party: "client", due_date: null, status: "open" }}
            onChange={(pending_items) => setDraft({ ...draft, pending_items })}
            disabled={isReadonly}
            renderItem={(p, set) => (
              <div className="grid gap-2 sm:grid-cols-[1fr_140px_120px]">
                <Textarea
                  rows={2}
                  placeholder="descrição"
                  value={p.description}
                  onChange={(e) => set({ ...p, description: e.target.value })}
                />
                <Input
                  placeholder="responsável"
                  value={p.owner_party ?? ""}
                  onChange={(e) => set({ ...p, owner_party: e.target.value || null })}
                />
                <Input
                  type="date"
                  value={p.due_date ?? ""}
                  onChange={(e) => set({ ...p, due_date: e.target.value || null })}
                />
              </div>
            )}
          />
        </TabsContent>

        <TabsContent value="hl">
          <Card>
            <CardHeader>
              <CardTitle>Destaques + Próximos passos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <Label>Destaques</Label>
                <Textarea
                  rows={5}
                  value={draft.highlights}
                  onChange={(e) => setDraft({ ...draft, highlights: e.target.value })}
                  disabled={isReadonly}
                />
              </div>
              <div className="space-y-1">
                <Label>Próximos passos</Label>
                <Textarea
                  rows={5}
                  value={draft.next_steps}
                  onChange={(e) => setDraft({ ...draft, next_steps: e.target.value })}
                  disabled={isReadonly}
                />
              </div>
              <div className="space-y-1">
                <Label>Notas internas</Label>
                <Textarea
                  rows={3}
                  value={draft.notes}
                  onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
                  disabled={isReadonly}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="mt-6 flex justify-end gap-3">
        <Button variant="outline" onClick={() => router.push(`/projetos/${projectId}/reports`)}>
          Voltar ao histórico
        </Button>
        {!isReadonly && (
          <Button onClick={handleSubmitFinal} disabled={submitting}>
            {submitting ? "Submetendo…" : "Submeter report"}
          </Button>
        )}
      </div>
    </AppShell>
  );
}

function SaveStatusBadge({ status, lastSavedAt }: { status: AutosaveStatus; lastSavedAt: Date | null }) {
  if (status === "saving") return <Badge variant="amber">salvando…</Badge>;
  if (status === "saved")
    return (
      <Badge variant="green">
        salvo {lastSavedAt ? `às ${lastSavedAt.toLocaleTimeString("pt-BR").slice(0, 5)}` : ""}
      </Badge>
    );
  if (status === "error") return <Badge variant="red">falha ao salvar</Badge>;
  return <Badge variant="outline">não há alterações</Badge>;
}

function ListEditor<T extends object>({
  title,
  items,
  empty,
  onChange,
  renderItem,
  disabled,
}: {
  title: string;
  items: T[];
  empty: T;
  onChange: (next: T[]) => void;
  renderItem: (item: T, set: (next: T) => void) => React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-end justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{items.length} item(ns)</CardDescription>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onChange([...items, empty])}
          disabled={disabled}
        >
          adicionar
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((item, i) => (
          <div key={i} className="rounded-md border p-3">
            {renderItem(item, (next) => {
              const arr = [...items];
              arr[i] = next;
              onChange(arr);
            })}
            <div className="mt-2 flex justify-end">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onChange(items.filter((_, j) => j !== i))}
                disabled={disabled}
              >
                remover
              </Button>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhum item adicionado.</p>
        )}
      </CardContent>
    </Card>
  );
}
