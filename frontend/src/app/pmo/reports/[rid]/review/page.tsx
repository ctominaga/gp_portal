"use client";

import {
  AlertTriangle,
  CheckCircle2,
  MessageSquarePlus,
  MessageSquareWarning,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, asApiError } from "@/lib/api";
import { ragColor, ragLabel, reportStatusLabel } from "@/lib/format";
import type { AIInsight, ApprovalRecord, Project, Report } from "@/lib/types";

const SEVERITY_BADGE: Record<string, "green" | "amber" | "red" | "outline"> = {
  info: "outline",
  low: "outline",
  medium: "amber",
  high: "red",
  critical: "red",
};

export default function ReviewReportPage() {
  const { rid } = useParams<{ rid: string }>();
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [decisionOpen, setDecisionOpen] = useState<
    "approved" | "approved_with_comment" | "requested_changes" | null
  >(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!rid) return;
    void (async () => {
      try {
        const rep = await api.get<Report>(`/reports/${rid}`);
        setReport(rep.data);
        const [proj, app, ins] = await Promise.all([
          api.get<Project>(`/projects/${rep.data.project_id}`),
          api.get<ApprovalRecord[]>(`/reports/${rid}/approvals`),
          api.get<AIInsight[]>(`/reports/${rid}/insights`),
        ]);
        setProject(proj.data);
        setApprovals(app.data);
        setInsights(ins.data);
      } catch (e) {
        toast.error(asApiError(e).message);
      }
    })();
  }, [rid]);

  async function decide() {
    if (!decisionOpen) return;
    const trimmed = comment.trim();
    if (decisionOpen === "requested_changes" && !trimmed) {
      toast.error("Comentário obrigatório para pedir revisão.");
      return;
    }
    if (decisionOpen === "approved_with_comment" && !trimmed) {
      toast.error("Comentário obrigatório para aprovar com nota interna.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/reports/${rid}/decide`, {
        decision: decisionOpen,
        comment: trimmed || null,
      });
      const msg =
        decisionOpen === "requested_changes"
          ? "Revisão solicitada"
          : decisionOpen === "approved_with_comment"
            ? "Report aprovado com nota interna ao GP"
            : "Report aprovado";
      toast.success(msg);
      router.replace("/pmo/portfolio");
    } catch (e) {
      toast.error(asApiError(e).message);
    } finally {
      setSubmitting(false);
      setDecisionOpen(null);
    }
  }

  if (!report || !project) {
    return (
      <AppShell>
        <p className="text-sm text-muted-foreground">Carregando…</p>
      </AppShell>
    );
  }

  const canDecide = report.status === "submitted";

  return (
    <AppShell>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">{project.client_name} · {project.name}</p>
          <h1 className="text-2xl font-semibold tracking-tight">
            Revisão de report ·{" "}
            {report.period_start} → {report.period_end}{" "}
            <Badge variant="secondary" className="ml-2">{reportStatusLabel(report.status)}</Badge>
          </h1>
        </div>
        {canDecide ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setDecisionOpen("requested_changes");
                setComment("");
              }}
            >
              <MessageSquareWarning className="mr-2 h-4 w-4" />
              Pedir revisão
            </Button>
            <Button
              variant="outline"
              className="border-primary/40 text-primary hover:bg-primary/5"
              onClick={() => {
                setDecisionOpen("approved_with_comment");
                setComment("");
              }}
            >
              <MessageSquarePlus className="mr-2 h-4 w-4" />
              Aprovar com comentário
            </Button>
            <Button
              onClick={() => {
                setDecisionOpen("approved");
                setComment("");
              }}
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Aprovar
            </Button>
          </div>
        ) : (
          <Badge variant="outline">decisão tomada</Badge>
        )}
      </div>

      {/* RAG por dimensão (resumo) */}
      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">Status por dimensão</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          {(["prazo", "escopo", "qualidade"] as const).map((dim) => {
            const v = report[`rag_${dim}` as `rag_${typeof dim}`] ?? null;
            const just = report[`rag_${dim}_justificativa` as `rag_${typeof dim}_justificativa`] ?? null;
            return (
              <div key={dim} className="space-y-1 rounded-md border p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium capitalize">{dim}</span>
                  {v ? <Badge variant={ragColor(v)}>{ragLabel(v)}</Badge> : <span className="text-xs">—</span>}
                </div>
                {just && <p className="text-xs italic text-muted-foreground">"{just}"</p>}
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* AIInsights */}
      {insights.length > 0 && (
        <Card className="mb-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              Análise do agente
            </CardTitle>
            <CardDescription>
              Padrões detectados pelo report_analyzer (stub em F4; agente real em F2.6).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights.map((ins) => (
              <div key={ins.id} className="rounded-md border-l-4 border-amber-400 bg-amber-50 p-3">
                <div className="mb-1 flex items-center gap-2">
                  <Badge variant={SEVERITY_BADGE[ins.payload.severity ?? "info"] ?? "outline"}>
                    {ins.payload.severity ?? "info"}
                  </Badge>
                  <strong className="text-sm">{ins.payload.headline}</strong>
                </div>
                {ins.payload.detail && (
                  <p className="text-xs text-amber-900">{ins.payload.detail}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Conteúdo do report (resumo) */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Destaques</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">
              {report.highlights ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Próximos passos</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">
              {report.next_steps ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Riscos abertos ({report.risks.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {report.risks.length === 0 && <p className="text-muted-foreground">—</p>}
            {report.risks.map((r, i) => {
              const lvl = r.level ?? "medium";
              const variant = lvl === "critical" || lvl === "high" ? "red"
                : lvl === "medium" ? "amber" : "outline";
              return (
                <div key={i} className="flex items-start gap-2">
                  <Badge variant={variant}>{lvl}</Badge>
                  <span className="flex-1">
                    {r.description}
                    <span className="ml-1 text-xs text-muted-foreground">
                      (P:{r.probability}/I:{r.impact})
                    </span>
                  </span>
                </div>
              );
            })}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Pendências ({report.pending_items.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {report.pending_items.length === 0 && <p className="text-muted-foreground">—</p>}
            {report.pending_items.map((p, i) => (
              <div key={i} className="rounded-md border p-2">
                <div className="flex items-start gap-2">
                  <Badge variant="outline">{p.owner_party ?? "?"}</Badge>
                  <span className="flex-1">{p.description}</span>
                </div>
                {p.impact && (
                  <p className="mt-1 text-xs italic text-muted-foreground">
                    impacto: {p.impact}
                  </p>
                )}
                {p.created_at && (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Aberto em {new Date(p.created_at).toLocaleDateString("pt-BR")}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
        {/* spec v3.1 §4.2.4 — planos de ação com vinculação visível ao PMO */}
        {report.action_plans.length > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">
                Planos de ação ({report.action_plans.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {report.action_plans.map((a, i) => (
                <div
                  key={i}
                  className="rounded-md border p-2"
                  title={a.objective || undefined}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={a.status === "done" ? "green" : a.status === "in_progress" ? "amber" : "outline"}>
                      {a.status}
                    </Badge>
                    <span className="flex-1">{a.description}</span>
                  </div>
                  {(a.linked_risk_description || a.linked_deliverable_title) && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {a.linked_risk_description && (
                        <span className="mr-2">
                          → vinculado ao risco: <em>{a.linked_risk_description}</em>
                        </span>
                      )}
                      {a.linked_deliverable_title && (
                        <span>
                          → vinculado ao entregável: <em>{a.linked_deliverable_title}</em>
                        </span>
                      )}
                    </p>
                  )}
                  {a.objective && (
                    <p className="mt-1 text-xs italic text-muted-foreground">
                      objetivo: {a.objective}
                    </p>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      {approvals.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-base">Histórico de decisões</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {approvals.map((a) => {
              const Icon =
                a.decision === "approved"
                  ? CheckCircle2
                  : a.decision === "approved_with_comment"
                    ? MessageSquarePlus
                    : MessageSquareWarning;
              const label =
                a.decision === "approved"
                  ? "Aprovado direto"
                  : a.decision === "approved_with_comment"
                    ? "Aprovado com comentário"
                    : "Revisão pedida";
              const tone =
                a.decision === "requested_changes"
                  ? "text-amber-700"
                  : "text-emerald-700";
              return (
                <div key={a.id} className="rounded-md border p-2 text-xs">
                  <div className={`flex items-center gap-2 ${tone}`}>
                    <Icon className="h-3.5 w-3.5" />
                    <strong className="capitalize">{a.stage}</strong>
                    <span>·</span>
                    <Badge variant="outline">{label}</Badge>
                    <span className="text-muted-foreground">· {a.decided_at}</span>
                  </div>
                  {a.comment && (
                    <p className="pt-1 italic">
                      {a.decision === "approved_with_comment" && (
                        <span className="not-italic mr-1 text-primary">
                          [nota interna]
                        </span>
                      )}
                      &ldquo;{a.comment}&rdquo;
                    </p>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Dialog de decisão — 3 caminhos (spec v3.1 §10.1) */}
      <Dialog open={decisionOpen !== null} onOpenChange={(o) => !o && setDecisionOpen(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {decisionOpen === "approved" && "Aprovar report"}
              {decisionOpen === "approved_with_comment" && "Aprovar com comentário"}
              {decisionOpen === "requested_changes" && "Pedir revisão"}
            </DialogTitle>
            <DialogDescription>
              {decisionOpen === "approved" &&
                "Aprova o report e o libera para o cliente confirmar leitura. Sem nota interna."}
              {decisionOpen === "approved_with_comment" && (
                <>
                  Aprova o report e libera para o cliente. O comentário é{" "}
                  <strong className="text-primary">nota interna ao GP</strong>,{" "}
                  <strong>não aparece no portal do cliente</strong>.
                </>
              )}
              {decisionOpen === "requested_changes" &&
                "Comentário obrigatório. O GP recebe notificação in-app e por e-mail explicando o que ajustar."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label className="text-sm">
              Comentário{" "}
              {(decisionOpen === "requested_changes" ||
                decisionOpen === "approved_with_comment") && (
                <span className="text-destructive">*</span>
              )}
            </Label>
            <Textarea
              rows={4}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder={
                decisionOpen === "approved"
                  ? "(opcional) bom report, parabéns à equipe"
                  : decisionOpen === "approved_with_comment"
                    ? "Ex.: aprovado, mas atenção a X no próximo report"
                    : "Explique o que precisa ser revisto…"
              }
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDecisionOpen(null)} disabled={submitting}>
              Cancelar
            </Button>
            <Button onClick={decide} disabled={submitting}>
              {submitting
                ? "Enviando…"
                : decisionOpen === "approved"
                  ? "Sim, aprovar"
                  : decisionOpen === "approved_with_comment"
                    ? "Sim, aprovar com nota"
                    : "Sim, pedir revisão"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
