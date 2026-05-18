"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, asApiError } from "@/lib/api";
import { reportCreateSchema, type ReportCreateInput } from "@/lib/schemas";
import type { Report, ReportSummary } from "@/lib/types";

// F5.4 — backend retorna 409 com formato "Já existe report no período X-Y.
// Acesse-o em /reports/{uuid}." quando há duplicação. Extrai o ID para
// abrir modal com link clicável em vez de toast cru.
function extractReportIdFromConflict(message: string): string | null {
  const match = message.match(/\/reports\/([0-9a-f-]{36})/i);
  return match ? match[1]! : null;
}

type Mode = "prepopulate" | "scratch";

export default function NewReportPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  // null = ainda carregando; false/true = decisão tomada
  const [hasPreviousReport, setHasPreviousReport] = useState<boolean | null>(null);
  const [mode, setMode] = useState<Mode>("scratch");
  // Estado do modal de conflito (409 — período já existe). null = fechado.
  const [conflict, setConflict] = useState<{ reportId: string; message: string } | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ReportCreateInput>({ resolver: zodResolver(reportCreateSchema) });

  useEffect(() => {
    if (!projectId) return;
    void (async () => {
      try {
        const r = await api.get<ReportSummary[]>(`/projects/${projectId}/reports`);
        const exists = r.data.length > 0;
        setHasPreviousReport(exists);
        // Pré-marca o modo mais útil: pré-popular se há report anterior,
        // do zero se é o primeiro report do projeto.
        setMode(exists ? "prepopulate" : "scratch");
      } catch {
        // Falha não-fatal: assume sem report anterior; UI mostra só "Do zero".
        setHasPreviousReport(false);
        setMode("scratch");
      }
    })();
  }, [projectId]);

  async function onSubmit(values: ReportCreateInput) {
    setSubmitting(true);
    try {
      let report: Report;
      if (mode === "prepopulate") {
        const r = await api.post<Report>(
          `/projects/${projectId}/reports/prepopulate`,
          values,
        );
        report = r.data;
      } else {
        const r = await api.post<Report>("/reports", {
          project_id: projectId,
          ...values,
        });
        report = r.data;
      }
      router.replace(`/projetos/${projectId}/reports/${report.id}/edit`);
    } catch (e) {
      const err = asApiError(e);
      // 409 do prepopulate (período duplicado) — extrai o report_id da
      // mensagem e abre modal com link clicável. Outros 409 (baseline
      // inativo) e demais erros caem no toast genérico.
      const existingId =
        err.status === 409 ? extractReportIdFromConflict(err.message) : null;
      if (existingId) {
        setConflict({ reportId: existingId, message: err.message });
      } else {
        toast.error(err.message);
      }
      setSubmitting(false);
    }
  }

  return (
    <AppShell>
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <CardTitle>Novo report</CardTitle>
          <CardDescription>
            Defina o período e escolha como começar. Você pode aproveitar o
            report anterior como ponto de partida (riscos abertos, pendências
            do cliente e entregas no prazo do período).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Modo</legend>
              <label
                className={
                  "flex cursor-pointer items-start gap-3 rounded-md border p-3 text-sm " +
                  (mode === "prepopulate"
                    ? "border-primary bg-primary/5"
                    : "border-input")
                }
              >
                <input
                  type="radio"
                  name="mode"
                  value="prepopulate"
                  checked={mode === "prepopulate"}
                  onChange={() => setMode("prepopulate")}
                  disabled={hasPreviousReport === false}
                  className="mt-0.5"
                  data-testid="radio-prepopulate"
                />
                <div className="flex-1">
                  <p className="flex items-center gap-1.5 font-medium">
                    <Sparkles className="h-4 w-4 text-primary" />
                    Pré-popular do report anterior
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Herda riscos abertos, pendências em aberto e cria
                    placeholders para entregas com prazo no período. Cada
                    item recebe um marcador &ldquo;do anterior&rdquo; que some quando
                    você edita.
                  </p>
                  {hasPreviousReport === false && (
                    <p
                      className="mt-1 text-xs italic text-muted-foreground"
                      data-testid="prepopulate-disabled-hint"
                    >
                      Sem report anterior — primeiro report do projeto.
                    </p>
                  )}
                </div>
              </label>

              <label
                className={
                  "flex cursor-pointer items-start gap-3 rounded-md border p-3 text-sm " +
                  (mode === "scratch" ? "border-primary bg-primary/5" : "border-input")
                }
              >
                <input
                  type="radio"
                  name="mode"
                  value="scratch"
                  checked={mode === "scratch"}
                  onChange={() => setMode("scratch")}
                  className="mt-0.5"
                  data-testid="radio-scratch"
                />
                <div className="flex-1">
                  <p className="font-medium">Começar do zero</p>
                  <p className="text-xs text-muted-foreground">
                    Wizard vazio. Você preenche cada seção manualmente.
                  </p>
                </div>
              </label>
            </fieldset>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="period_start">Início *</Label>
                <Input id="period_start" type="date" {...register("period_start")} />
                {errors.period_start && (
                  <p className="text-xs text-destructive">{errors.period_start.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="period_end">Fim *</Label>
                <Input id="period_end" type="date" {...register("period_end")} />
                {errors.period_end && (
                  <p className="text-xs text-destructive">{errors.period_end.message}</p>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" asChild>
                <Link href={`/projetos/${projectId}`}>Cancelar</Link>
              </Button>
              <Button type="submit" disabled={submitting} data-testid="btn-submit">
                {submitting ? "Criando…" : "Criar e abrir wizard"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Dialog
        open={conflict !== null}
        onOpenChange={(o) => {
          if (!o) setConflict(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Report já existe nesse período</DialogTitle>
            <DialogDescription>
              {conflict?.message ??
                "Já existe um report cobrindo essas datas. Você pode abrir o existente ou escolher outro período."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConflict(null)}>
              Escolher outro período
            </Button>
            {conflict && (
              <Button asChild data-testid="btn-open-existing-report">
                <Link
                  href={`/projetos/${projectId}/reports/${conflict.reportId}/edit`}
                >
                  Abrir report existente
                </Link>
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
