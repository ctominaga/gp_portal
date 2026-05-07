"use client";

import { useEffect, useRef, useState } from "react";

export type AutosaveStatus = "idle" | "saving" | "saved" | "error";

/**
 * Debounce + persist. Recebe `value` (qualquer objeto) e `save(value)`,
 * dispara `save` ~debounceMs após mudanças. Retorna status para a UI.
 */
export function useAutosave<T>(
  value: T,
  save: (v: T) => Promise<void>,
  options: { debounceMs?: number; enabled?: boolean } = {},
): { status: AutosaveStatus; lastSavedAt: Date | null; flush: () => Promise<void> } {
  const { debounceMs = 800, enabled = true } = options;
  const [status, setStatus] = useState<AutosaveStatus>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialRef = useRef<string | null>(null);
  const valueRef = useRef<T>(value);

  useEffect(() => {
    valueRef.current = value;
  }, [value]);

  const doSave = async () => {
    setStatus("saving");
    try {
      await save(valueRef.current);
      setStatus("saved");
      setLastSavedAt(new Date());
    } catch {
      setStatus("error");
    }
  };

  useEffect(() => {
    if (!enabled) return;
    const serialized = JSON.stringify(value);
    if (initialRef.current === null) {
      initialRef.current = serialized;
      return;
    }
    if (initialRef.current === serialized) return;
    initialRef.current = serialized;

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      void doSave();
    }, debounceMs);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(value), enabled, debounceMs]);

  const flush = async () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    await doSave();
  };

  return { status, lastSavedAt, flush };
}
