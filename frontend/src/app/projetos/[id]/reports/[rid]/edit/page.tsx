"use client";

import { CheckCircle2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, asApiError } from "@/lib/api";
import { useAutosave, type AutosaveStatus } from "@/lib/hooks/use-autosave";
import {
  DIMENSION_LABELS,
  RAG_OPTIONS,
  type Dimension,
  type RagDraft,
  validateRag,
} from "@/lib/rag";
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
  // Dimensões independentes (F3.5.3+4)
  rag_prazo: RAGStatus | null;
  rag_escopo: RAGStatus | null;
  rag_qualidade: RAGStatus | null;
  rag_prazo_justificativa: string;
  rag_escopo_justificativa: string;
  rag_qualidade_justificativa: string;
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
    rag_prazo: r.rag_prazo ?? null,
    rag_escopo: r.rag_escopo ?? null,
    rag_qualidade: r.rag_qualidade ?? null,
    rag_prazo_justificativa: r.rag_prazo_justificativa ?? "",
    rag_escopo_justificativa: r.rag_escopo_justificativa ?? "",
    rag_qualidade_justificativa: r.rag_qualidade_justificativa ?? "",
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
  const [acceptanceConfirm, setAcceptanceConfirm] = useState<{ index: number } | null>(null);

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

  // Pré-popula progresses com deliverables do baseline ativo
  useEffect(() => {
    if (!draft || !activeBaseline) return;
    if (draft.progresses.length > 0) return;
    const seeded: DeliveryProgress[] = activeBaseline.deliverables.map((d) => ({
      deliverable_id: d.id,
      status: "planned",
      percent_complete: 0,
      comment: null,
      revised_date: null,
    }));
    setDraft({ ...draft, progresses: seeded });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBaseline]);

  const save = useCallback(
    async (d: DraftState) => {
      const payload: Record<string, unknown> = {
        period_start: d.period_start,
        period_end: d.period_end,
        rag_prazo: d.rag_prazo,
        rag_escopo: d.rag_escopo,
        rag_qualidade: d.rag_qualidade,
        rag_prazo_justificativa: d.rag_prazo_justificativa || null,
        rag_escopo_justificativa: d.rag_escopo_justificativa || null,
        rag_qualidade_justificativa: d.rag_qualidade_justificativa || null,
        highlights: d.highlights || null,
        next_steps: d.next_steps || null,
        notes: d.notes || null,
        progresses: d.progresses.map((p) => ({
          deliverable_id: p.deliverable_id,
          status: p.status,
          percent_complete: p.percent_complete,
          comment: p.comment,
          revised_date: p.revised_date || null,
        })),
        risks: d.risks.map((r) => ({
          description: r.description,
          probability: r.probability,
          impact: r.impact,
          mitigation_plan: r.mitigation_plan,
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

  const ragDraft: RagDraft | null = draft && {
    rag_prazo: draft.rag_prazo,
    rag_escopo: draft.rag_escopo,
    rag_qualidade: draft.rag_qualidade,
    rag_prazo_justificativa: draft.rag_prazo_justificativa,
    rag_escopo_justificativa: draft.rag_escopo_justificativa,
    rag_qualidade_justificativa: draft.rag_qualidade_justificativa,
  };
  const ragValidation = ragDraft ? validateRag(ragDraft) : null;
  const ragBlocking =
    !ragValidation ||
    !ragValidation.ok ||
    ragValidation.missingDimensions.length > 0 ||
    ragValidation.missingJustifications.length > 0;

  async function handleSubmitFinal() {
    if (!draft || !rid || !ragValidation) return;
    if (!ragValidation.ok) {
      if (ragValidation.missingDimensions.length > 0) {
        toast.error(
          `Preencha todas as dimensões: ${ragValidation.missingDimensions
            .map((d) => DIMENSION_LABELS[d])
            .join(", ")}`,
        );
      } else if (ragValidation.missingJustifications.length > 0) {
        toast.error(
          `Justificativa obrigatória para Amarelo/Vermelho em: ${ragValidation.missingJustifications
            .map((d) => DIMENSION_LABELS[d])
            .join(", ")}`,
        );
      }
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
          <TabsTrigger value="rag">
            2. RAG{ragValidation && !ragValidation.ok ? " ⚠" : ""}
          </TabsTrigger>
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

        {/* F3.5.3+4: 3 dimensões independentes + justificativa obrigatória A/R */}
        <TabsContent value="rag">
          <Card>
            <CardHeader>
              <CardTitle>Status RAG por dimensão</CardTitle>
              <CardDescription>
                Avalie Prazo, Escopo e Qualidade separadamente. O agregado do report é
                derivado pelo backend (worst-of-3). Justificativa é obrigatória para Amarelo
                ou Vermelho em qualquer dimensão.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {(["prazo", "escopo", "qualidade"] as const).map((dim) => (
                <RagDimensionRow
                  key={dim}
                  dim={dim}
                  value={
                    dim === "prazo"
                      ? draft.rag_prazo
                      : dim === "escopo"
                        ? draft.rag_escopo
                        : draft.rag_qualidade
                  }
                  justificativa={
                    dim === "prazo"
                      ? draft.rag_prazo_justificativa
                      : dim === "escopo"
                        ? draft.rag_escopo_justificativa
                        : draft.rag_qualidade_justificativa
                  }
                  onChange={(val, just) => {
                    setDraft({
                      ...draft,
                      [`rag_${dim}`]: val,
                      [`rag_${dim}_justificativa`]: just,
                    } as DraftState);
                  }}
                  disabled={isReadonly}
                />
              ))}

              {ragValidation && !ragValidation.ok && (
                <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                  {ragValidation.missingDimensions.length > 0 && (
                    <p>
                      Faltam dimensões: <strong>
                        {ragValidation.missingDimensions
                          .map((d) => DIMENSION_LABELS[d])
                          .join(", ")}
                      </strong>
                    </p>
                  )}
                  {ragValidation.missingJustifications.length > 0 && (
                    <p>
                      Justificativa obrigatória para status Amarelo/Vermelho em:{" "}
                      <strong>
                        {ragValidation.missingJustifications
                          .map((d) => DIMENSION_LABELS[d])
                          .join(", ")}
                      </strong>
                    </p>
                  )}
                </div>
              )}
              {ragValidation?.ok && ragValidation.aggregate && (
                <p className="text-xs text-muted-foreground">
                  Agregado (worst-of-3):{" "}
                  <Badge
                    variant={
                      ragValidation.aggregate === "G"
                        ? "green"
                        : ragValidation.aggregate === "A"
                          ? "amber"
                          : "red"
                    }
                  >
                    {ragValidation.aggregate}
                  </Badge>
                </p>
              )}
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
                const showRevisedDate = p.status !== "done" && p.percent_complete < 100;
                const plannedDate = d?.due_date ?? null;
                // F4-débito.B: "desvio" só faz sentido depois que a entrega
                // começou — em "Planejado" o re-planejamento é normal, não desvio.
                const hasDeviation =
                  showRevisedDate &&
                  p.status !== "planned" &&
                  !!p.revised_date &&
                  !!plannedDate &&
                  p.revised_date !== plannedDate;
                return (
                  <div
                    key={p.deliverable_id}
                    className="grid gap-3 rounded-md border p-3 sm:grid-cols-[1fr_140px_120px_140px]"
                  >
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium">
                          {d?.code ? `${d.code} · ` : ""}
                          {d?.title ?? p.deliverable_id}
                        </p>
                        {/* spec v3.1 §4.2.2: badge quando GP confirmou critério de aceite */}
                        {p.acceptance_confirmed === true && (
                          <Badge variant="green" className="gap-1 text-xs">
                            <CheckCircle2 className="h-3 w-3" /> aceite confirmado
                          </Badge>
                        )}
                      </div>
                      {d?.phase && (
                        <p className="text-xs text-muted-foreground">{d.phase}</p>
                      )}
                      {plannedDate && (
                        <p className="text-xs text-muted-foreground">
                          Prazo planejado: {plannedDate}
                        </p>
                      )}
                    </div>
                    <Select
                      value={p.status}
                      onValueChange={(v) => {
                        // F3.5.6: confirmação inline ao marcar Concluído + 100%
                        if (v === "done" && p.percent_complete >= 100) {
                          setAcceptanceConfirm({ index: i });
                          return;
                        }
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
                        const pct = Number(e.target.value || 0);
                        const next = [...draft.progresses];
                        // F3.5.6: se chegar a 100 com status já "done", confirma
                        if (pct === 100 && p.status === "done") {
                          setAcceptanceConfirm({ index: i });
                          return;
                        }
                        next[i] = { ...p, percent_complete: pct };
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

                    {/* F3.5.5: revised_date quando ainda não concluído */}
                    {showRevisedDate && (
                      <div className="sm:col-span-4">
                        <div className="flex items-end gap-3">
                          <div className="flex-1 space-y-1">
                            <Label className="text-xs">
                              Data revisada de entrega{" "}
                              {hasDeviation && (
                                <Badge variant="amber" className="ml-1 align-middle">
                                  desvio
                                </Badge>
                              )}
                            </Label>
                            <Input
                              type="date"
                              value={p.revised_date ?? ""}
                              onChange={(e) => {
                                const next = [...draft.progresses];
                                next[i] = { ...p, revised_date: e.target.value || null };
                                setDraft({ ...draft, progresses: next });
                              }}
                              disabled={isReadonly}
                            />
                          </div>
                          {plannedDate && (
                            <p className="pb-2 text-xs text-muted-foreground">
                              vs. planejado {plannedDate}
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>

          {/* F3.5.6: dialog de confirmação de critério de aceite */}
          <Dialog
            open={acceptanceConfirm !== null}
            onOpenChange={(o) => !o && setAcceptanceConfirm(null)}
          >
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                  Critério de aceite foi atingido?
                </DialogTitle>
                <DialogDescription>
                  Marcar este entregável como Concluído com 100% indica que o critério de
                  aceite foi cumprido. Isso entra no Health Score do projeto. Deseja
                  continuar?
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="ghost" onClick={() => setAcceptanceConfirm(null)}>
                  Cancelar
                </Button>
                <Button
                  onClick={() => {
                    if (acceptanceConfirm === null) return;
                    const next = [...draft.progresses];
                    const i = acceptanceConfirm.index;
                    // spec v3.1 §4.2.2: persistir acceptance_confirmed=true.
                    // Backend rejeita salvar status=done + 100% sem esta flag.
                    next[i] = {
                      ...next[i],
                      status: "done",
                      percent_complete: 100,
                      acceptance_confirmed: true,
                    };
                    setDraft({ ...draft, progresses: next });
                    setAcceptanceConfirm(null);
                  }}
                >
                  Sim, concluído
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        <TabsContent value="risks">
          <ListEditor<Risk>
            title="Riscos"
            items={draft.risks}
            empty={{
              description: "",
              probability: "media",
              impact: "medio",
              mitigation_plan: null,
              owner_id: null,
              due_date: null,
              status: "identified",
            }}
            onChange={(risks) => setDraft({ ...draft, risks })}
            disabled={isReadonly}
            renderItem={(r, set) => {
              // spec v3.1 §4.2.3 — level derivado da matriz Prob×Impact.
              // Replica a matriz do backend (compute_risk_level) — visual only.
              const levelOf = (p: Risk["probability"], i: Risk["impact"]): Risk["level"] => {
                const m: Record<string, Risk["level"]> = {
                  "alta-alto": "critical", "alta-medio": "high", "alta-baixo": "medium",
                  "media-alto": "high", "media-medio": "medium", "media-baixo": "low",
                  "baixa-alto": "medium", "baixa-medio": "low", "baixa-baixo": "low",
                };
                return m[`${p}-${i}`];
              };
              const lvl = levelOf(r.probability, r.impact);
              const lvlVariant = lvl === "critical" || lvl === "high" ? "red" : lvl === "medium" ? "amber" : "outline";
              return (
                <div className="grid gap-2 sm:grid-cols-[1fr_120px_120px_120px]">
                  <Textarea
                    rows={2}
                    placeholder="descrição do risco"
                    value={r.description}
                    onChange={(e) => set({ ...r, description: e.target.value })}
                  />
                  <div className="space-y-1">
                    <Label className="text-xs">Probabilidade</Label>
                    <Select
                      value={r.probability}
                      onValueChange={(v) => set({ ...r, probability: v as Risk["probability"] })}
                    >
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="alta">Alta</SelectItem>
                        <SelectItem value="media">Média</SelectItem>
                        <SelectItem value="baixa">Baixa</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Impacto</Label>
                    <Select
                      value={r.impact}
                      onValueChange={(v) => set({ ...r, impact: v as Risk["impact"] })}
                    >
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="alto">Alto</SelectItem>
                        <SelectItem value="medio">Médio</SelectItem>
                        <SelectItem value="baixo">Baixo</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Nível (derivado)</Label>
                    <div className="pt-1">
                      <Badge variant={lvlVariant}>{lvl}</Badge>
                    </div>
                  </div>
                  <div className="sm:col-span-4">
                    <Label className="text-xs">Plano de mitigação</Label>
                    <Textarea
                      rows={2}
                      placeholder="o que será feito para evitar/reduzir"
                      value={r.mitigation_plan ?? ""}
                      onChange={(e) =>
                        set({ ...r, mitigation_plan: e.target.value || null })
                      }
                    />
                  </div>
                </div>
              );
            }}
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
          <Button
            onClick={handleSubmitFinal}
            disabled={submitting || ragBlocking}
            title={
              ragBlocking ? "Preencha as 3 dimensões e justificativas obrigatórias" : undefined
            }
          >
            {submitting ? "Submetendo…" : "Submeter report"}
          </Button>
        )}
      </div>
    </AppShell>
  );
}

function RagDimensionRow({
  dim,
  value,
  justificativa,
  onChange,
  disabled,
}: {
  dim: Dimension;
  value: RAGStatus | null;
  justificativa: string;
  onChange: (val: RAGStatus | null, just: string) => void;
  disabled?: boolean;
}) {
  const needsJustification = (value === "A" || value === "R") && justificativa.trim().length === 0;
  return (
    <div className="space-y-2 rounded-md border p-4">
      <div className="flex items-center justify-between">
        <Label className="text-base font-medium">{DIMENSION_LABELS[dim]}</Label>
        <div className="flex gap-2">
          {RAG_OPTIONS.map((opt) => (
            <Button
              key={opt}
              type="button"
              size="sm"
              variant={value === opt ? "default" : "outline"}
              className={
                value === opt
                  ? opt === "G"
                    ? "bg-green-600 hover:bg-green-600/90"
                    : opt === "A"
                      ? "bg-amber-500 hover:bg-amber-500/90"
                      : "bg-red-600 hover:bg-red-600/90"
                  : ""
              }
              onClick={() => onChange(opt, justificativa)}
              disabled={disabled}
            >
              {opt === "G" ? "Verde" : opt === "A" ? "Amarelo" : "Vermelho"}
            </Button>
          ))}
        </div>
      </div>
      {(value === "A" || value === "R") && (
        <div className="space-y-1">
          <Label className="text-xs">
            Justificativa <span className="text-destructive">*</span> (obrigatória para A/R)
          </Label>
          <Textarea
            rows={2}
            placeholder={`Por que ${DIMENSION_LABELS[dim]} está em ${
              value === "A" ? "Amarelo" : "Vermelho"
            }?`}
            value={justificativa}
            onChange={(e) => onChange(value, e.target.value)}
            disabled={disabled}
          />
          {needsJustification && (
            <p className="text-xs text-destructive">
              Justificativa obrigatória para status Amarelo/Vermelho.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function SaveStatusBadge({
  status,
  lastSavedAt,
}: {
  status: AutosaveStatus;
  lastSavedAt: Date | null;
}) {
  const time = lastSavedAt
    ? lastSavedAt.toLocaleTimeString("pt-BR").slice(0, 5)
    : null;
  if (status === "saving") {
    return <Badge variant="amber">salvando…</Badge>;
  }
  if (status === "saved") {
    return (
      <Badge variant="green" className="gap-1">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Salvo {time ? `às ${time}` : ""}
      </Badge>
    );
  }
  if (status === "error") {
    return <Badge variant="red">falha ao salvar</Badge>;
  }
  // idle
  return (
    <Badge variant="outline" className="gap-1">
      <CheckCircle2 className="h-3.5 w-3.5" />
      Tudo salvo
    </Badge>
  );
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
