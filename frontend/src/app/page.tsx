import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <main className="container mx-auto flex min-h-screen flex-col items-center justify-center gap-8 py-12">
      <div className="space-y-2 text-center">
        <h1 className="text-4xl font-bold tracking-tight">Jump GP Portal</h1>
        <p className="text-lg text-muted-foreground">
          Sistema de Report e Gestão Estratégica de Projetos
        </p>
      </div>

      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>Status do ambiente</CardTitle>
          <CardDescription>
            F0 — scaffolding inicial. Frontend e backend rodam via docker compose.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-4">
          <Button asChild>
            <Link href="/health-check">Verificar saúde do backend</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="https://github.com/ctominaga/gp_portal" target="_blank">
              Repositório
            </Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
