"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, asApiError } from "@/lib/api";
import { projectCreateSchema, type ProjectCreateInput } from "@/lib/schemas";

export default function NewProjectPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProjectCreateInput>({ resolver: zodResolver(projectCreateSchema) });

  async function onSubmit(values: ProjectCreateInput) {
    setSubmitting(true);
    const payload: Record<string, unknown> = {
      name: values.name,
      client_name: values.client_name,
    };
    if (values.description) payload.description = values.description;
    if (values.started_at) payload.started_at = values.started_at;
    if (values.client_user_email) payload.client_user_email = values.client_user_email;

    try {
      const r = await api.post<{ id: string }>("/projects", payload);
      toast.success("Projeto criado");
      router.replace(`/projetos/${r.data.id}`);
    } catch (e) {
      toast.error(asApiError(e).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppShell>
      <Card className="mx-auto max-w-2xl">
        <CardHeader>
          <CardTitle>Novo projeto</CardTitle>
          <CardDescription>Cadastre o cliente e o escopo. A proposta vem em seguida.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nome do projeto *</Label>
              <Input id="name" placeholder="Ex.: Migração SAS para Databricks" {...register("name")} />
              {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="client_name">Cliente *</Label>
              <Input id="client_name" placeholder="Ex.: Bradesco" {...register("client_name")} />
              {errors.client_name && (
                <p className="text-xs text-destructive">{errors.client_name.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Descrição</Label>
              <Textarea id="description" rows={4} {...register("description")} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="started_at">Data de início</Label>
                <Input id="started_at" type="date" {...register("started_at")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="client_user_email">E-mail do contato cliente</Label>
                <Input
                  id="client_user_email"
                  type="email"
                  placeholder="(opcional, deve ter conta com role CLIENT)"
                  {...register("client_user_email")}
                />
                {errors.client_user_email && (
                  <p className="text-xs text-destructive">{errors.client_user_email.message}</p>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <Button type="button" variant="ghost" asChild>
                <Link href="/projetos">Cancelar</Link>
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Criando…" : "Criar projeto"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </AppShell>
  );
}
