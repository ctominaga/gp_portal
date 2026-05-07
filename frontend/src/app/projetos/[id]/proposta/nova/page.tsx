"use client";

import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, asApiError } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { Proposal } from "@/lib/types";

export default function ProposalUploadPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function pick(f: File | null) {
    if (!f) return;
    if (!f.type.includes("pdf") && !f.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Envie um PDF da proposta");
      return;
    }
    setFile(f);
  }

  async function upload() {
    if (!file || !projectId) return;
    setSubmitting(true);
    setProgress(0);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post<Proposal>(`/projects/${projectId}/proposals`, fd, {
        onUploadProgress: (e) => {
          if (e.total) setProgress(Math.round((e.loaded / e.total) * 100));
        },
      });
      toast.success("Proposta enviada — extraindo baseline…");
      router.replace(`/projetos/${projectId}/proposta/${r.data.id}`);
    } catch (e) {
      toast.error(asApiError(e).message);
      setSubmitting(false);
      setProgress(null);
    }
  }

  return (
    <AppShell>
      <Card className="mx-auto max-w-2xl">
        <CardHeader>
          <CardTitle>Enviar proposta</CardTitle>
          <CardDescription>
            PDF da proposta. A extração do baseline é assíncrona — você será
            notificado quando estiver pronto para revisão.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" ? inputRef.current?.click() : null)}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              pick(e.dataTransfer.files[0] ?? null);
            }}
            role="button"
            tabIndex={0}
            className={`flex h-40 cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed transition-colors ${
              dragOver ? "border-primary bg-primary/5" : "border-input"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => pick(e.target.files?.[0] ?? null)}
            />
            {file ? (
              <div className="text-center">
                <p className="font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
              </div>
            ) : (
              <div className="text-center text-sm text-muted-foreground">
                <p>Arraste o PDF aqui ou clique para selecionar</p>
                <p className="text-xs">Tamanho recomendado: até 50MB</p>
              </div>
            )}
          </div>
          {progress !== null && (
            <div className="space-y-1 text-xs text-muted-foreground">
              <div className="h-2 w-full overflow-hidden rounded bg-muted">
                <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
              </div>
              <p>Enviando: {progress}%</p>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" disabled={submitting} onClick={() => router.back()}>
              Cancelar
            </Button>
            <Button onClick={upload} disabled={!file || submitting}>
              {submitting ? "Enviando…" : "Enviar e extrair"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </AppShell>
  );
}
