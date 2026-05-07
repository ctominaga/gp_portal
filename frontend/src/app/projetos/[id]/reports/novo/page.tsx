"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, asApiError } from "@/lib/api";
import { reportCreateSchema, type ReportCreateInput } from "@/lib/schemas";
import type { Report } from "@/lib/types";

export default function NewReportPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ReportCreateInput>({ resolver: zodResolver(reportCreateSchema) });

  async function onSubmit(values: ReportCreateInput) {
    setSubmitting(true);
    try {
      const r = await api.post<Report>("/reports", { project_id: projectId, ...values });
      router.replace(`/projetos/${projectId}/reports/${r.data.id}/edit`);
    } catch (e) {
      toast.error(asApiError(e).message);
      setSubmitting(false);
    }
  }

  return (
    <AppShell>
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <CardTitle>Novo report</CardTitle>
          <CardDescription>Defina o período e siga para o wizard.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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
              <Button type="submit" disabled={submitting}>
                {submitting ? "Criando…" : "Criar e abrir wizard"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </AppShell>
  );
}
