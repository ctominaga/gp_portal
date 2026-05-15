"use client";

import { AlertTriangle, FilePlus2, ShieldCheck } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { apiAdminDataRequests, asApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type {
  DataProcessingRecord,
  DPRequestStatus,
  DPRequestType,
} from "@/lib/types";

const STATUS_OPTIONS: { value: DPRequestStatus | "all"; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "pending", label: "Pendente" },
  { value: "fulfilled", label: "Atendido" },
  { value: "rejected", label: "Rejeitado" },
  { value: "approved", label: "Aprovado" },
];

const TYPE_OPTIONS: { value: DPRequestType | "all"; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "deletion", label: "Eliminação" },
  { value: "export", label: "Portabilidade" },
  { value: "access", label: "Acesso" },
  { value: "rectification", label: "Retificação" },
];

const STATUS_BADGE: Record<DPRequestStatus, "secondary" | "green" | "red" | "amber"> = {
  pending: "amber",
  approved: "secondary",
  fulfilled: "green",
  rejected: "red",
};

const TYPE_LABEL: Record<DPRequestType, string> = {
  deletion: "Eliminação",
  export: "Portabilidade",
  access: "Acesso",
  rectification: "Retificação",
};

function subjectLabel(record: DataProcessingRecord): string {
  if (record.subject_external_email) return record.subject_external_email;
  if (record.subject_user_id) return `Interno · ${record.subject_user_id.slice(0, 8)}`;
  return "—";
}

export default function AdminDataRequestsPage() {
  const [records, setRecords] = useState<DataProcessingRecord[] | null>(null);
  const [statusFilter, setStatusFilter] = useState<DPRequestStatus | "all">("pending");
  const [typeFilter, setTypeFilter] = useState<DPRequestType | "all">("all");

  // Estado dos dois modais.
  const [createOpen, setCreateOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formEmail, setFormEmail] = useState("");
  const [formType, setFormType] = useState<DPRequestType>("deletion");
  const [formNotes, setFormNotes] = useState("");

  const [fulfillTarget, setFulfillTarget] = useState<DataProcessingRecord | null>(null);
  const [fulfilling, setFulfilling] = useState(false);

  const load = useMemo(
    () => async () => {
      try {
        const r = await apiAdminDataRequests.list({
          status: statusFilter === "all" ? undefined : statusFilter,
          request_type: typeFilter === "all" ? undefined : typeFilter,
        });
        setRecords(r.items);
      } catch (e) {
        toast.error(asApiError(e).message);
      }
    },
    [statusFilter, typeFilter],
  );

  useEffect(() => {
    setRecords(null);
    void load();
  }, [load]);

  async function onCreate(): Promise<void> {
    if (!formEmail.trim()) {
      toast.error("Informe o e-mail do titular.");
      return;
    }
    setSubmitting(true);
    try {
      await apiAdminDataRequests.createManual({
        subject_external_email: formEmail.trim(),
        request_type: formType,
        notes: formNotes.trim() || null,
      });
      toast.success("Pedido manual registrado.");
      setCreateOpen(false);
      setFormEmail("");
      setFormType("deletion");
      setFormNotes("");
      await load();
    } catch (e) {
      toast.error(asApiError(e).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function onFulfill(): Promise<void> {
    if (!fulfillTarget) return;
    setFulfilling(true);
    try {
      await apiAdminDataRequests.fulfill(fulfillTarget.id);
      toast.success("Pedido marcado como atendido.");
      setFulfillTarget(null);
      await load();
    } catch (e) {
      toast.error(asApiError(e).message);
    } finally {
      setFulfilling(false);
    }
  }

  const isDeletionWithInternalSubject =
    fulfillTarget?.request_type === "deletion" &&
    fulfillTarget?.subject_user_id !== null &&
    fulfillTarget?.subject_user_id !== undefined;

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">Admin</p>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <ShieldCheck className="h-6 w-6" />
            Pedidos LGPD
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Registro de Atividades de Tratamento (RAT). Atender pedidos é
            irreversível — leia <code>docs/lgpd.md</code> antes.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} data-testid="btn-new-manual">
          <FilePlus2 className="mr-2 h-4 w-4" />
          Novo pedido manual
        </Button>
      </div>

      <Card className="mb-4">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filtros</CardTitle>
          <CardDescription>
            Filtre por status e tipo do pedido. Default exibe os pendentes.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">
              Status
            </Label>
            <Select
              value={statusFilter}
              onValueChange={(v) =>
                setStatusFilter(v as DPRequestStatus | "all")
              }
            >
              <SelectTrigger data-testid="filter-status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">
              Tipo
            </Label>
            <Select
              value={typeFilter}
              onValueChange={(v) =>
                setTypeFilter(v as DPRequestType | "all")
              }
            >
              <SelectTrigger data-testid="filter-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TYPE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {records === null ? (
        <Skeleton className="h-72" />
      ) : records.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Nenhum pedido encontrado para os filtros atuais.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-left">Titular</th>
                  <th className="px-4 py-3 text-left">Tipo</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Pedido em</th>
                  <th className="px-4 py-3 text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {records.map((rec) => (
                  <tr
                    key={rec.id}
                    className="border-b last:border-0 hover:bg-muted/20"
                    data-testid={`record-row-${rec.id}`}
                  >
                    <td className="px-4 py-3 font-medium">
                      {subjectLabel(rec)}
                    </td>
                    <td className="px-4 py-3">{TYPE_LABEL[rec.request_type]}</td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_BADGE[rec.status]}>
                        {rec.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(rec.requested_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={rec.status === "fulfilled"}
                        onClick={() => setFulfillTarget(rec)}
                        data-testid={`btn-fulfill-${rec.id}`}
                      >
                        Atender
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Modal: novo pedido manual */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Novo pedido manual</DialogTitle>
            <DialogDescription>
              Registre um pedido LGPD recebido pelo canal externo
              (christopher.tominaga@jumplabel.com.br ou outro canal documentado).
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="space-y-1">
              <Label htmlFor="manual-email">E-mail do titular</Label>
              <Input
                id="manual-email"
                type="email"
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                placeholder="titular@empresa.com"
                data-testid="manual-email"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="manual-type">Tipo do pedido</Label>
              <Select
                value={formType}
                onValueChange={(v) => setFormType(v as DPRequestType)}
              >
                <SelectTrigger id="manual-type" data-testid="manual-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TYPE_OPTIONS.filter((o) => o.value !== "all").map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="manual-notes">Notas (opcional)</Label>
              <Textarea
                id="manual-notes"
                rows={3}
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                placeholder="Contexto do pedido, canal de origem, prazo combinado…"
                data-testid="manual-notes"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setCreateOpen(false)}
              disabled={submitting}
            >
              Cancelar
            </Button>
            <Button
              onClick={onCreate}
              disabled={submitting}
              data-testid="btn-create-confirm"
            >
              {submitting ? "Registrando…" : "Registrar pedido"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal: atender pedido */}
      <Dialog
        open={fulfillTarget !== null}
        onOpenChange={(open) => {
          if (!open) setFulfillTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Atender pedido
            </DialogTitle>
            <DialogDescription>
              Esta ação é <strong>irreversível</strong>.
              {isDeletionWithInternalSubject ? (
                <>
                  {" "}
                  O titular interno será anonimizado: <code>name</code>,{" "}
                  <code>email</code> e <code>password_hash</code> serão zerados
                  e <code>anonymized_at</code> receberá o carimbo. O usuário
                  perderá acesso ao Sistema.
                </>
              ) : (
                <> O pedido será marcado como atendido no RAT.</>
              )}
            </DialogDescription>
          </DialogHeader>
          {fulfillTarget && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div>
                <strong>Titular:</strong> {subjectLabel(fulfillTarget)}
              </div>
              <div>
                <strong>Tipo:</strong> {TYPE_LABEL[fulfillTarget.request_type]}
              </div>
              <div>
                <strong>Pedido em:</strong>{" "}
                {formatDate(fulfillTarget.requested_at)}
              </div>
              {fulfillTarget.notes && (
                <div>
                  <strong>Notas:</strong> {fulfillTarget.notes}
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setFulfillTarget(null)}
              disabled={fulfilling}
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={onFulfill}
              disabled={fulfilling}
              data-testid="btn-fulfill-confirm"
            >
              {fulfilling ? "Atendendo…" : "Confirmar atendimento"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
