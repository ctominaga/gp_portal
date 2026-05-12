"use client";

import { ArrowLeftRight, CheckCircle2, MinusCircle, PencilLine, PlusCircle, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/auth-context";
import { api, asApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { BaselineDiff, ScopeChange, TransitionResult } from "@/lib/types";

interface BaselineRow {
  id: string;
  proposal_id: string;
  status: string;
  activated_at: string | null;
  created_at: string;
  deliverable_count: number;
  source_proposal_filename: string | null;
  source_proposal_version: number | null;
}

export default function ProjectDiffPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();
  const [baselines, setBaselines] = useState<BaselineRow[] | null>(null);
  const [baseId, setBaseId] = useState<string>("");
  const [newId, setNewId] = useState<string>("");
  const [diff, setDiff] = useState<BaselineDiff | null>(null);
  const [loadingDiff, setLoadingDiff] = useState(false);
  // F5.2 — ScopeChanges PROPOSED do baseline_to selecionado. PMO usa para
  // saber se há transição revisável; GP/Cliente vê só badge informativo.
  const [pendingScs, setPendingScs] = useState<ScopeChange[]>([]);
  const [dialogMode, setDialogMode] = useState<"approve" | "reject" | null>(null);
  const [commentInput, setCommentInput] = useState("");
  const [submittingDecision, setSubmittingDecision] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    void (async () => {
      try {
        const r = await api.get<BaselineRow[]>(`/projects/${projectId}/baselines`);
        setBaselines(r.data);
        // Pre-seleção: query string > newest 2
        const qNew = searchParams.get("new");
        const qBase = searchParams.get("base");
        if (qNew && r.data.some((b) => b.id === qNew)) {
          setNewId(qNew);
        } else if (r.data[0]) {
          setNewId(r.data[0].id);
        }
        if (qBase && r.data.some((b) => b.id === qBase)) {
          setBaseId(qBase);
        } else if (r.data[1]) {
          setBaseId(r.data[1].id);
        }
      } catch (e) {
        toast.error(asApiError(e).message);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (!baseId || !newId || baseId === newId) {
      setDiff(null);
      return;
    }
    setLoadingDiff(true);
    void (async () => {
      try {
        const r = await api.get<BaselineDiff>(`/client/diff/${baseId}/${newId}`);
        setDiff(r.data);
      } catch (e) {
        toast.error(asApiError(e).message);
      } finally {
        setLoadingDiff(false);
      }
    })();
  }, [baseId, newId]);

  // F5.2 — carrega ScopeChanges PROPOSED apontando para o `newId`. Tanto PMO
  // (decide) quanto GP (vê badge "aguardando PMO") usam.
  useEffect(() => {
    if (!projectId || !newId) {
      setPendingScs([]);
      return;
    }
    void (async () => {
      try {
        const r = await api.get<ScopeChange[]>(
          `/projects/${projectId}/scope-changes?status=proposed&baseline_to_id=${newId}`,
        );
        setPendingScs(r.data);
      } catch {
        // não-fatal: sem PROPOSED a tela do diff segue funcionando read-only
        setPendingScs([]);
      }
    })();
  }, [projectId, newId]);

  async function handleTransitionSubmit() {
    if (!dialogMode || !newId) return;
    if (dialogMode === "reject" && !commentInput.trim()) {
      toast.error("Justificativa obrigatória para rejeitar a transição.");
      return;
    }
    setSubmittingDecision(true);
    try {
      const r = await api.post<TransitionResult>(
        `/baselines/${newId}/transition`,
        {
          decision: dialogMode,
          comment: commentInput.trim() || null,
        },
      );
      const verb = dialogMode === "approve" ? "aprovada" : "rejeitada";
      toast.success(
        `Transição ${verb} — ${r.data.scope_changes_count} alteração(ões) processada(s)`,
      );
      // UX pós-decisão: leva para o portfólio PMO (lista atualizada) em vez
      // de ficar na tela do diff, agora obsoleta para este baseline_to.
      router.push("/pmo/portfolio");
    } catch (e) {
      toast.error(asApiError(e).message);
    } finally {
      setSubmittingDecision(false);
      setDialogMode(null);
      setCommentInput("");
    }
  }

  const isPMO = user?.role === "PMO";
  const hasPendingTransition = pendingScs.length > 0;
  const newBaseline = baselines?.find((b) => b.id === newId);
  const baseBaseline = baselines?.find((b) => b.id === baseId);

  const labelOf = useMemo(
    () => (id: string) => {
      const b = baselines?.find((x) => x.id === id);
      if (!b) return id;
      const v = b.source_proposal_version ? `v${b.source_proposal_version}` : "—";
      return `${v} · ${b.deliverable_count} entr. · ${formatDate(b.created_at)} (${b.status})`;
    },
    [baselines],
  );

  if (!baselines) {
    return (
      <AppShell>
        <Skeleton className="h-96" />
      </AppShell>
    );
  }

  const sameBaseline = baseId && newId && baseId === newId;

  return (
    <AppShell>
      <div className="mb-6">
        <p className="text-sm text-muted-foreground">
          <Link href={`/projetos/${projectId}`} className="hover:underline">
            ← voltar ao projeto
          </Link>
        </p>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <ArrowLeftRight className="h-6 w-6" />
          Comparar baselines
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Cada item adicionado, removido ou alterado entre versões gera um{" "}
          <strong>ScopeChange</strong> quando o worker importa a nova proposta.
        </p>
      </div>

      {hasPendingTransition && (
        <Card className="mb-6 border-amber-300 bg-amber-50/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              {isPMO
                ? "Transição aguardando sua decisão"
                : "Transição aguardando aprovação do PMO"}
            </CardTitle>
            <CardDescription>
              {pendingScs.length} alteração(ões) propostas pelo GP em{" "}
              {newBaseline?.source_proposal_version
                ? `v${newBaseline.source_proposal_version}`
                : "v?"}
              {baseBaseline?.source_proposal_version
                ? ` (vs v${baseBaseline.source_proposal_version})`
                : ""}
              . {isPMO ? "Revise abaixo e aprove/rejeite a transição." : "GP não pode ativar v2+ sem aprovação."}
            </CardDescription>
          </CardHeader>
          {isPMO && (
            <CardContent className="flex flex-wrap gap-2">
              <Button
                onClick={() => {
                  setDialogMode("approve");
                  setCommentInput("");
                }}
                disabled={submittingDecision}
                data-testid="btn-approve-transition"
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Aprovar transição
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  setDialogMode("reject");
                  setCommentInput("");
                }}
                disabled={submittingDecision}
                data-testid="btn-reject-transition"
              >
                <XCircle className="mr-2 h-4 w-4" />
                Rejeitar transição
              </Button>
            </CardContent>
          )}
        </Card>
      )}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Selecione as versões</CardTitle>
          <CardDescription>
            Compara os entregáveis usando <em>código</em> como chave. Sem código, o item não
            aparece no diff.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              Versão base (anterior)
            </label>
            <Select value={baseId} onValueChange={setBaseId}>
              <SelectTrigger>
                <SelectValue placeholder="Escolha uma baseline" />
              </SelectTrigger>
              <SelectContent>
                {baselines.map((b) => (
                  <SelectItem key={b.id} value={b.id}>
                    {labelOf(b.id)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              Versão nova
            </label>
            <Select value={newId} onValueChange={setNewId}>
              <SelectTrigger>
                <SelectValue placeholder="Escolha uma baseline" />
              </SelectTrigger>
              <SelectContent>
                {baselines.map((b) => (
                  <SelectItem key={b.id} value={b.id}>
                    {labelOf(b.id)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Dialog
        open={dialogMode !== null}
        onOpenChange={(o) => {
          if (!submittingDecision && !o) setDialogMode(null);
        }}
      >
        <DialogContent>
          {dialogMode === "approve" && (
            <>
              <DialogHeader>
                <DialogTitle>Aprovar transição</DialogTitle>
                <DialogDescription>
                  Esta ação vai aprovar <strong>{pendingScs.length}</strong>{" "}
                  alteração(ões) de escopo e tornar o baseline{" "}
                  <strong>v{newBaseline?.source_proposal_version ?? "?"}</strong>{" "}
                  o ativo do projeto. O baseline anterior será marcado como
                  histórico (SUPERSEDED). <strong>Ação irreversível.</strong>
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wide text-muted-foreground">
                  Comentário (opcional)
                </label>
                <Textarea
                  value={commentInput}
                  onChange={(e) => setCommentInput(e.target.value)}
                  placeholder="Ex.: aprovado conforme alinhamento em reunião 12/05"
                  rows={3}
                />
              </div>
              <DialogFooter>
                <Button
                  variant="ghost"
                  onClick={() => setDialogMode(null)}
                  disabled={submittingDecision}
                >
                  Cancelar
                </Button>
                <Button
                  onClick={handleTransitionSubmit}
                  disabled={submittingDecision}
                  data-testid="confirm-approve"
                >
                  {submittingDecision ? "Aprovando…" : "Confirmar aprovação"}
                </Button>
              </DialogFooter>
            </>
          )}
          {dialogMode === "reject" && (
            <>
              <DialogHeader>
                <DialogTitle>Rejeitar transição</DialogTitle>
                <DialogDescription>
                  Esta ação vai rejeitar <strong>{pendingScs.length}</strong>{" "}
                  alteração(ões) de escopo e marcar o baseline{" "}
                  <strong>v{newBaseline?.source_proposal_version ?? "?"}</strong>{" "}
                  como rejeitado. O baseline anterior permanece ativo. GP
                  precisa ressubmeter uma nova versão para tentar nova mudança.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wide text-muted-foreground">
                  Justificativa (obrigatória — será enviada ao GP)
                </label>
                <Textarea
                  value={commentInput}
                  onChange={(e) => setCommentInput(e.target.value)}
                  placeholder="Ex.: faltou detalhamento do critério de aceite no d-007"
                  rows={3}
                  required
                />
              </div>
              <DialogFooter>
                <Button
                  variant="ghost"
                  onClick={() => setDialogMode(null)}
                  disabled={submittingDecision}
                >
                  Cancelar
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleTransitionSubmit}
                  disabled={submittingDecision || !commentInput.trim()}
                  data-testid="confirm-reject"
                >
                  {submittingDecision ? "Rejeitando…" : "Confirmar rejeição"}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {sameBaseline ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Selecione duas baselines diferentes para comparar.
          </CardContent>
        </Card>
      ) : loadingDiff ? (
        <Skeleton className="h-64" />
      ) : diff ? (
        <DiffSection diff={diff} />
      ) : (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Selecione duas baselines acima para visualizar a comparação.
          </CardContent>
        </Card>
      )}
    </AppShell>
  );
}

function DiffSection({ diff }: { diff: BaselineDiff }) {
  const totalChanges = diff.added.length + diff.removed.length + diff.changed.length;

  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total de mudanças</CardDescription>
            <CardTitle className="text-3xl">{totalChanges}</CardTitle>
          </CardHeader>
        </Card>
        <Card className={diff.added.length ? "border-green-300" : ""}>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <PlusCircle className="h-3.5 w-3.5 text-green-600" /> Adicionados
            </CardDescription>
            <CardTitle className="text-3xl text-green-700">{diff.added.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card className={diff.removed.length ? "border-red-300" : ""}>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <MinusCircle className="h-3.5 w-3.5 text-red-600" /> Removidos
            </CardDescription>
            <CardTitle className="text-3xl text-red-700">{diff.removed.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card className={diff.changed.length ? "border-amber-300" : ""}>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <PencilLine className="h-3.5 w-3.5 text-amber-600" /> Alterados
            </CardDescription>
            <CardTitle className="text-3xl text-amber-700">{diff.changed.length}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {totalChanges === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Nenhuma diferença entre as versões selecionadas.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {diff.added.length > 0 && (
            <Card className="border-green-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-green-800">
                  <PlusCircle className="h-4 w-4" />
                  Entregáveis adicionados ({diff.added.length})
                </CardTitle>
                <CardDescription>
                  Cada item adicionado gerou um ScopeChange quando o worker importou a nova
                  proposta.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {diff.added.map((d, i) => (
                  <div key={i} className="rounded-md border border-green-200 bg-green-50 p-3 text-sm">
                    <div className="flex items-center gap-2">
                      <Badge variant="green">{d.code}</Badge>
                      <strong>{d.title_new}</strong>
                    </div>
                    <p className="pt-1 text-xs text-muted-foreground">
                      Fase: {d.phase_new ?? "—"} · Complexidade: {d.complexity_new ?? "—"}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {diff.removed.length > 0 && (
            <Card className="border-red-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-red-800">
                  <MinusCircle className="h-4 w-4" />
                  Entregáveis removidos ({diff.removed.length})
                </CardTitle>
                <CardDescription>
                  Itens que estavam na baseline anterior mas não aparecem na nova.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {diff.removed.map((d, i) => (
                  <div key={i} className="rounded-md border border-red-200 bg-red-50 p-3 text-sm">
                    <div className="flex items-center gap-2">
                      <Badge variant="red">{d.code}</Badge>
                      <strong className="line-through opacity-70">{d.title_old}</strong>
                    </div>
                    <p className="pt-1 text-xs text-muted-foreground">
                      Fase: {d.phase_old ?? "—"} · Complexidade: {d.complexity_old ?? "—"}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {diff.changed.length > 0 && (
            <Card className="border-amber-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-amber-800">
                  <PencilLine className="h-4 w-4" />
                  Entregáveis alterados ({diff.changed.length})
                </CardTitle>
                <CardDescription>
                  Mesma chave (código) mas título, fase ou complexidade mudaram.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {diff.changed.map((d, i) => (
                  <div key={i} className="rounded-md border border-amber-200 bg-amber-50/50 p-3 text-sm">
                    <div className="mb-2 flex items-center gap-2">
                      <Badge variant="amber">{d.code}</Badge>
                      <strong className="text-amber-900">alterado</strong>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">
                          antes
                        </p>
                        <p className="font-medium text-red-700 line-through opacity-70">
                          {d.title_old}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          fase: {d.phase_old ?? "—"} · compl.: {d.complexity_old ?? "—"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">
                          depois
                        </p>
                        <p className="font-medium text-green-700">{d.title_new}</p>
                        <p className="text-xs text-muted-foreground">
                          fase: {d.phase_new ?? "—"} · compl.: {d.complexity_new ?? "—"}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </>
  );
}
