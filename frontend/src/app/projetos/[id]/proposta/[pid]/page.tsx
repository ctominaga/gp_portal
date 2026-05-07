"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, asApiError } from "@/lib/api";
import { useSSE } from "@/lib/hooks/use-sse";
import { formatBytes, formatDate, proposalStatusLabel } from "@/lib/format";
import type { Baseline, Proposal } from "@/lib/types";

export default function ProposalDetailPage() {
  const { id: projectId, pid } = useParams<{ id: string; pid: string }>();
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [baselineId, setBaselineId] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const r = await api.get<Proposal>(`/projects/${projectId}/proposals/${pid}`);
      setProposal(r.data);
      if (r.data.status === "extracted") {
        // Busca o baseline (draft) gerado a partir desta proposal
        try {
          const list = await api.get<Baseline | null>(`/projects/${projectId}/active-baseline`);
          if (list.data) setBaselineId(list.data.id);
        } catch {
          // se não existe ainda, ignora
        }
      }
    } catch (e) {
      toast.error(asApiError(e).message);
    }
  }, [projectId, pid]);

  useEffect(() => {
    if (projectId && pid) void refetch();
  }, [projectId, pid, refetch]);

  // SSE: quando proposal_extracted bate, recarrega
  useSSE(
    useCallback(
      (event, data) => {
        if (event === "proposal_extracted" && data && typeof data === "object") {
          const p = (data as { proposal_id?: string; baseline_id?: string }).proposal_id;
          if (p === pid) {
            void refetch();
            const bid = (data as { baseline_id?: string }).baseline_id;
            if (bid) setBaselineId(bid);
            toast.success("Baseline pronto para revisão!");
          }
        }
      },
      [pid, refetch],
    ),
  );

  // Polling fallback caso SSE não conecte (ex: dev sem auth)
  useEffect(() => {
    if (!proposal || proposal.status !== "pending_extraction") return;
    const t = setInterval(() => void refetch(), 4000);
    return () => clearInterval(t);
  }, [proposal, refetch]);

  if (!proposal) {
    return (
      <AppShell>
        <p className="text-sm text-muted-foreground">Carregando…</p>
      </AppShell>
    );
  }

  const isExtracting = proposal.status === "pending_extraction";

  return (
    <AppShell>
      <Card className="mx-auto max-w-2xl">
        <CardHeader className="space-y-2">
          <div className="flex items-center justify-between">
            <CardTitle>Proposta v{proposal.version}</CardTitle>
            <Badge
              variant={
                proposal.status === "extracted"
                  ? "green"
                  : proposal.status === "pending_extraction"
                    ? "amber"
                    : "secondary"
              }
            >
              {proposalStatusLabel(proposal.status)}
            </Badge>
          </div>
          <CardDescription>
            {proposal.original_filename} · {formatBytes(proposal.size_bytes)} · enviada em{" "}
            {formatDate(proposal.uploaded_at)}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {isExtracting && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-4 text-amber-900">
              <p className="font-medium">Extraindo baseline…</p>
              <p className="text-xs">
                Estamos lendo a proposta com o agente leitor. Pode levar alguns minutos.
                Você será notificado em tempo real quando estiver pronta para revisão.
              </p>
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded bg-amber-200">
                <div className="h-full w-1/2 animate-pulse bg-amber-500" />
              </div>
            </div>
          )}

          {proposal.status === "extracted" && baselineId && (
            <div className="rounded-md border border-green-300 bg-green-50 p-4 text-green-900">
              <p className="font-medium">Baseline pronto.</p>
              <p className="text-xs">
                Revise os entregáveis extraídos antes de ativar.
              </p>
              <div className="mt-3">
                <Button asChild>
                  <Link href={`/projetos/${projectId}/baseline/${baselineId}`}>
                    Revisar baseline
                  </Link>
                </Button>
              </div>
            </div>
          )}

          {proposal.status === "needs_ocr" && (
            <div className="rounded-md border bg-muted p-4 text-muted-foreground">
              <p className="font-medium text-foreground">Necessita OCR</p>
              <p className="text-xs">
                A proposta é majoritariamente imagem; o agente leitor não conseguiu
                extrair texto. O backlog deve ser cadastrado manualmente nesse caso.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </AppShell>
  );
}
