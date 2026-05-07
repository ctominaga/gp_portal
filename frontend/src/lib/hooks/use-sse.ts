"use client";

import { useEffect } from "react";

import { getToken } from "@/lib/api";

const baseURL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type EventHandler = (event: string, data: unknown) => void;

/**
 * Conexão SSE simples que escuta o stream `/events/stream`.
 * Como o navegador EventSource não suporta headers customizados, usamos
 * fetch + ReadableStream para passar o Authorization Bearer.
 */
export function useSSE(onEvent: EventHandler, options: { enabled?: boolean } = {}) {
  const enabled = options.enabled ?? true;

  useEffect(() => {
    if (!enabled) return;
    const token = getToken();
    if (!token) return;

    const controller = new AbortController();
    let cancelled = false;

    void (async () => {
      try {
        const res = await fetch(`${baseURL}/events/stream`, {
          headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
          signal: controller.signal,
        });
        if (!res.ok || !res.body) return;
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";
          for (const frame of frames) {
            const lines = frame.split("\n");
            let event = "message";
            let dataRaw = "";
            for (const line of lines) {
              if (line.startsWith("event: ")) event = line.slice(7).trim();
              else if (line.startsWith("data: ")) dataRaw += line.slice(6);
            }
            if (!dataRaw) continue;
            try {
              onEvent(event, JSON.parse(dataRaw));
            } catch {
              onEvent(event, dataRaw);
            }
          }
        }
      } catch (e) {
        // AbortError é esperado quando desmonta
        if ((e as { name?: string }).name !== "AbortError") {
          console.warn("SSE error", e);
        }
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [enabled, onEvent]);
}
