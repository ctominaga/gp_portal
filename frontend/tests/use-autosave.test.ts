import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useAutosave } from "@/lib/hooks/use-autosave";

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

describe("useAutosave (real timers)", () => {
  it("não chama save no mount", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    renderHook(() => useAutosave({ a: 1 }, save, { debounceMs: 50 }));
    await wait(80);
    expect(save).not.toHaveBeenCalled();
  });

  it("chama save após mudança debounced", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { rerender } = renderHook(
      ({ value }: { value: { a: number } }) => useAutosave(value, save, { debounceMs: 30 }),
      { initialProps: { value: { a: 1 } } },
    );
    rerender({ value: { a: 2 } });
    await waitFor(() => expect(save).toHaveBeenCalledWith({ a: 2 }), { timeout: 1000 });
  });

  it("debounce coalesce mudanças rápidas", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { rerender } = renderHook(
      ({ value }: { value: { a: number } }) => useAutosave(value, save, { debounceMs: 60 }),
      { initialProps: { value: { a: 1 } } },
    );
    rerender({ value: { a: 2 } });
    rerender({ value: { a: 3 } });
    rerender({ value: { a: 4 } });
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1), { timeout: 1000 });
    expect(save).toHaveBeenLastCalledWith({ a: 4 });
  });

  it("status vira 'error' quando save rejeita", async () => {
    const save = vi.fn().mockRejectedValue(new Error("boom"));
    const { rerender, result } = renderHook(
      ({ value }: { value: { a: number } }) => useAutosave(value, save, { debounceMs: 30 }),
      { initialProps: { value: { a: 1 } } },
    );
    rerender({ value: { a: 2 } });
    await waitFor(() => expect(result.current.status).toBe("error"), { timeout: 1000 });
  });

  it("não dispara quando enabled=false", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { rerender } = renderHook(
      ({ value, enabled }: { value: { a: number }; enabled: boolean }) =>
        useAutosave(value, save, { debounceMs: 30, enabled }),
      { initialProps: { value: { a: 1 }, enabled: false } },
    );
    rerender({ value: { a: 2 }, enabled: false });
    await wait(80);
    expect(save).not.toHaveBeenCalled();
  });
});
