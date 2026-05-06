import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type HealthResponse = {
  status: "ok" | "degraded";
  db: "ok" | "down";
  redis: "ok" | "down";
  version?: string;
};

async function fetchHealth(): Promise<{ ok: boolean; data?: HealthResponse; error?: string }> {
  const url = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${url}/health`, { cache: "no-store" });
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
    const data = (await res.json()) as HealthResponse;
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export const dynamic = "force-dynamic";

export default async function HealthCheckPage() {
  const result = await fetchHealth();

  return (
    <main className="container mx-auto flex min-h-screen flex-col items-center justify-center gap-6 py-12">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>Health check</CardTitle>
          <CardDescription>Verifica conectividade com FastAPI, Postgres e Redis.</CardDescription>
        </CardHeader>
        <CardContent>
          {result.ok && result.data ? (
            <ul className="space-y-2 font-mono text-sm">
              <li>status: <strong>{result.data.status}</strong></li>
              <li>db: <strong>{result.data.db}</strong></li>
              <li>redis: <strong>{result.data.redis}</strong></li>
              {result.data.version ? <li>version: {result.data.version}</li> : null}
            </ul>
          ) : (
            <div className="text-destructive">
              Backend indisponível: {result.error ?? "erro desconhecido"}
            </div>
          )}
        </CardContent>
      </Card>
      <Button asChild variant="outline">
        <Link href="/">Voltar</Link>
      </Button>
    </main>
  );
}
