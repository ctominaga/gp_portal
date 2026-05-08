"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, asApiError } from "@/lib/api";
import { useSSE } from "@/lib/hooks/use-sse";
import type { InAppNotification } from "@/lib/types";

export function NotificationBell() {
  const [unread, setUnread] = useState<number>(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<InAppNotification[]>([]);

  const refreshCount = useCallback(async () => {
    try {
      const r = await api.get<{ unread: number }>("/notifications/unread-count");
      setUnread(r.data.unread);
    } catch {
      /* silencioso */
    }
  }, []);

  const fetchList = useCallback(async () => {
    try {
      const r = await api.get<InAppNotification[]>("/notifications");
      setItems(r.data);
    } catch (e) {
      console.warn(asApiError(e).message);
    }
  }, []);

  useEffect(() => {
    void refreshCount();
  }, [refreshCount]);

  useSSE(
    useCallback(
      (event) => {
        if (event === "notification") {
          void refreshCount();
          if (open) void fetchList();
        }
      },
      [refreshCount, fetchList, open],
    ),
  );

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next) await fetchList();
  }

  async function markRead(n: InAppNotification) {
    try {
      await api.post(`/notifications/${n.id}/read`);
      setItems((prev) => prev.map((it) => (it.id === n.id ? { ...it, read_at: new Date().toISOString() } : it)));
      void refreshCount();
    } catch (e) {
      console.warn(asApiError(e).message);
    }
  }

  return (
    <div className="relative">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={toggle}
        aria-label="Notificações"
        className="relative"
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <Badge
            variant="red"
            className="absolute -right-1 -top-1 h-4 min-w-[16px] justify-center px-1 text-[10px]"
          >
            {unread > 9 ? "9+" : unread}
          </Badge>
        )}
      </Button>
      {open && (
        <div className="absolute right-0 top-12 z-50 w-80 overflow-hidden rounded-md border bg-popover shadow-lg">
          <div className="flex items-center justify-between border-b px-3 py-2 text-xs">
            <strong>Notificações</strong>
            {unread > 0 && (
              <span className="text-muted-foreground">{unread} nova(s)</span>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 && (
              <p className="p-4 text-center text-xs text-muted-foreground">
                Sem notificações.
              </p>
            )}
            {items.map((n) => (
              <div
                key={n.id}
                className={`border-b px-3 py-2 text-sm last:border-0 ${
                  n.read_at ? "opacity-60" : ""
                }`}
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1">
                    <p className="font-medium">{n.title}</p>
                    {n.body && <p className="text-xs text-muted-foreground">{n.body}</p>}
                    {n.link && (
                      <Link
                        href={n.link}
                        className="text-xs text-primary underline-offset-2 hover:underline"
                        onClick={() => void markRead(n)}
                      >
                        abrir →
                      </Link>
                    )}
                  </div>
                  {!n.read_at && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 px-2 text-xs"
                      onClick={() => void markRead(n)}
                    >
                      ✓
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
