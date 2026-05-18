"use client";

import { AlertTriangle, ArrowLeft, FileWarning, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/auth-context";
import { api, asApiError } from "@/lib/api";
import type {
  MaterializedRiskItem,
  Project,
  ProjectCloseResult,
  Risk,
  RiskLevel,
} from "@/lib/types";

interface FormState {
  delivered_vs_proposed: string;
  would_do_differently: string;
  client_feedback: string;
  // Mapa risk_id → comment (null se ainda não comentado).
  // Presença na chave = marcado como materializado; ausência = não-marcado.
  materialized: Map<string, string | null>;
}

// Risks vindos de `/projects/{id}/risks` sempre têm id (assertion local).
// Tipo Risk global permite id opcional para suportar formulário de criação.
type RiskWithId = Risk & { id: string };

const LEVEL_VARIANT: Record<RiskLevel, "red" | "amber" | "secondary" | "outline"> = {
  critical: "red",
  high: "red",
  medium: "amber",
  low: "secondary",
};

const LEVEL_LABEL: Record<RiskLevel, string> = {
  critical: "Crítico",
  high: "Alto",
  medium: "Médio",
  low: "Baixo",
};

export default function ProjectClosePage() {
  const { id: projectId } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [risks, setRisks] = useState<RiskWithId[] | null>(null);
  const [form, setForm] = useState<FormState>({
    delivered_vs_proposed: "",
    would_do_differently: "",
    client_feedback: "",
    materialized: new Map(),
  });
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    void (async () => {
      try {
        const [p, r] = await Promise.all([
          api.get<Project>(`/projects/${projectId}`),
          api.get<Risk[]>(`/projects/${projectId}/risks`),
        ]);
        setProject(p.data);
        // Filtra para garantir o `id` (backend sempre devolve, mas o tipo
        // Risk permite undefined para suportar forms de criação).
        const withId = r.data.filter((rk): rk is RiskWithId => Boolean(rk.id));
        setRisks(withId);
        // Pré-seleção (decisão Q1 híbrida): risks com status=materialized
        // entram marcados; GP pode adicionar/remover livremente.
        const pre = new Map<string, string | null>();
        for (const risk of withId) {
          if (risk.status === "materialized") pre.set(risk.id, null);
        }
        setForm((f) => ({ ...f, materialized: pre }));
      } catch (e) {
        toast.error(asApiError(e).message);
      }
    })();
  }, [projectId]);

  const isOwnerGP = useMemo(
    () => Boolean(project && user && user.role === "GP" && project.gp_user_id === user.id),
    [project, user],
  );
  const isActive = project?.status === "active";
  const canSubmit =
    isOwnerGP &&
    isActive &&
    form.delivered_vs_proposed.trim().length > 0 &&
    form.would_do_differently.trim().length > 0 &&
    form.client_feedback.trim().length > 0;

  function toggleRisk(risk_id: string) {
    setForm((f) => {
      const next = new Map(f.materialized);
      if (next.has(risk_id)) {
        next.delete(risk_id);
      } else {
        next.set(risk_id, null);
      }
      return { ...f, materialized: next };
    });
  }

  function updateRiskComment(risk_id: string, comment: string) {
    setForm((f) => {
      const next = new Map(f.materialized);
      if (next.has(risk_id)) next.set(risk_id, comment || null);
      return { ...f, materialized: next };
    });
  }

  async function handleSubmit() {
    if (!canSubmit || !projectId) return;
    setSubmitting(true);
    try {
      const payload = {
        delivered_vs_proposed: form.delivered_vs_proposed,
        would_do_differently: form.would_do_differently,
        client_feedback: form.client_feedback,
        materialized_risks: Array.from(form.materialized.entries()).map(
          ([risk_id, comment]) => ({ risk_id, comment } satisfies MaterializedRiskItem),
        ),
      };
      const r = await api.post<ProjectCloseResult>(
        `/projects/${projectId}/close`,
        payload,
      );
      toast.success("Projeto encerrado com sucesso.");
      router.push(`/projetos/${r.data.project_id}`);
    } catch (e) {
      const err = asApiError(e);
      // 409 do backend já carrega a mensagem específica com ação concreta
      // (cascata Q4 — vide /api/v1/projects.py). 422 pode ser risk_id inválido
      // ou campo vazio (validação Pydantic). Em ambos, mostrar mensagem cru
      // do servidor — UI confia que backend formula bem.
      toast.error(err.message);
    } finally {
      setSubmitting(false);
      setConfirmOpen(false);
    }
  }

  if (!project || risks === null) {
    return (
      <AppShell>
        <Skeleton className="h-96" />
      </AppShell>
    );
  }

  if (!isOwnerGP) {
    return (
      <AppShell>
        <Card>
          <CardHeader>
            <CardTitle>Acesso negado</CardTitle>
            <CardDescription>
              Apenas o GP responsável pelo projeto pode iniciar o encerramento.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link href={`/projetos/${projectId}`}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Voltar ao projeto
              </Link>
            </Button>
          </CardContent>
        </Card>
      </AppShell>
    );
  }

  if (!isActive) {
    return (
      <AppShell>
        <Card>
          <CardHeader>
            <CardTitle>Projeto não está ativo</CardTitle>
            <CardDescription>
              Apenas projetos com status <code>active</code> podem ser encerrados.
              Estado atual: <strong>{project.status}</strong>.
            </CardDescription>
          </CardHeader>
        </Card>
      </AppShell>
    );
  }

  const materializedCount = form.materialized.size;
  const today = new Date().toISOString().slice(0, 10);

  return (
    <AppShell>
      <div className="mb-6">
        <p className="text-sm text-muted-foreground">
          <Link href={`/projetos/${projectId}`} className="hover:underline">
            ← voltar ao projeto
          </Link>
        </p>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <ShieldCheck className="h-6 w-6" />
          Encerrar projeto: {project.name}
        </h1>
      </div>

      <Card className="mb-6 border-amber-300 bg-amber-50/40">
        <CardContent className="flex items-start gap-3 py-4 text-sm">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
          <p>
            <strong>Ação irreversível.</strong> Revise com atenção antes de
            confirmar. A retrospectiva preenchida abaixo será preservada
            permanentemente e alimenta o agente de inteligência cruzada do
            portfólio (v3.1 §10.4).
          </p>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Entregue vs. Proposto</CardTitle>
            <CardDescription>
              O que foi efetivamente entregue comparado ao escopo original aprovado.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={4}
              placeholder="Ex.: 9 dos 12 entregáveis aprovados foram concluídos. Sprint 4 movida para o backlog do próximo projeto por mudança de prioridade do cliente."
              value={form.delivered_vs_proposed}
              onChange={(e) =>
                setForm((f) => ({ ...f, delivered_vs_proposed: e.target.value }))
              }
              data-testid="input-delivered"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">O que faria diferente</CardTitle>
            <CardDescription>
              Lições aprendidas acionáveis para projetos similares.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={4}
              placeholder="Ex.: criar plano de contingência regulatório no início; alinhar critérios de aceite com a área de Risco antes do kickoff."
              value={form.would_do_differently}
              onChange={(e) =>
                setForm((f) => ({ ...f, would_do_differently: e.target.value }))
              }
              data-testid="input-would-diff"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Feedback do cliente</CardTitle>
            <CardDescription>
              Resumo do feedback recebido. Pontos positivos e áreas de melhoria.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={4}
              placeholder="Ex.: cliente satisfeito com a governança e ritmo de entregas; sinalizou que esperava mais atenção nos relatórios regulatórios da fase 3."
              value={form.client_feedback}
              onChange={(e) =>
                setForm((f) => ({ ...f, client_feedback: e.target.value }))
              }
              data-testid="input-client-feedback"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileWarning className="h-5 w-5 text-amber-700" />
              Riscos materializados
            </CardTitle>
            <CardDescription>
              Marque os riscos que viraram problema durante o projeto. Riscos com
              status <strong>materializado</strong> já vêm pré-marcados (você pode
              adicionar ou remover livremente). Comentário &ldquo;como foi tratado&rdquo; é
              opcional por item.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {risks.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                Nenhum risco registrado neste projeto.
              </p>
            ) : (
              risks.map((risk) => {
                const checked = form.materialized.has(risk.id);
                const comment = form.materialized.get(risk.id) ?? "";
                return (
                  <div
                    key={risk.id}
                    className={
                      "rounded-md border p-3 text-sm " +
                      (checked ? "border-amber-300 bg-amber-50/50" : "border-input")
                    }
                  >
                    <label className="flex items-start gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleRisk(risk.id)}
                        className="mt-1 h-4 w-4"
                        data-testid={`risk-checkbox-${risk.id}`}
                      />
                      <div className="flex-1 space-y-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {risk.level && (
                            <Badge variant={LEVEL_VARIANT[risk.level]}>
                              {LEVEL_LABEL[risk.level]}
                            </Badge>
                          )}
                          <Badge variant="outline">{risk.status}</Badge>
                        </div>
                        <p>{risk.description}</p>
                      </div>
                    </label>
                    {checked && (
                      <Textarea
                        rows={2}
                        placeholder="Como foi tratado? (opcional)"
                        value={comment}
                        onChange={(e) => updateRiskComment(risk.id, e.target.value)}
                        className="mt-2"
                        data-testid={`risk-comment-${risk.id}`}
                      />
                    )}
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        <div className="flex flex-wrap gap-3 pt-2">
          <Button asChild variant="ghost">
            <Link href={`/projetos/${projectId}`}>Cancelar</Link>
          </Button>
          <Button
            variant="destructive"
            disabled={!canSubmit || submitting}
            onClick={() => setConfirmOpen(true)}
            data-testid="btn-open-confirm"
          >
            Encerrar projeto
          </Button>
        </div>
      </div>

      <Dialog
        open={confirmOpen}
        onOpenChange={(o) => {
          if (!submitting && !o) setConfirmOpen(false);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar encerramento</DialogTitle>
            <DialogDescription>
              Esta ação é <strong>IRREVERSÍVEL</strong>. Após confirmar:
            </DialogDescription>
          </DialogHeader>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Projeto vai para status <code>CLOSED</code></li>
            <li>Data de encerramento: <strong>{today}</strong></li>
            <li>A retrospectiva será preservada permanentemente</li>
            <li>
              {materializedCount} risco(s) será(ão) registrado(s) como
              materializado(s)
            </li>
          </ul>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setConfirmOpen(false)}
              disabled={submitting}
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={handleSubmit}
              disabled={submitting}
              data-testid="btn-confirm-close"
            >
              {submitting ? "Encerrando…" : "Confirmar encerramento"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
