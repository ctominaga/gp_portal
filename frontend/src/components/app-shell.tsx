"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center text-muted-foreground">
        Carregando…
      </main>
    );
  }
  if (!user) return null;

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
        <div className="container mx-auto flex h-14 items-center gap-6">
          <Link href="/dashboard" className="font-semibold tracking-tight">
            Jump GP Portal
          </Link>
          <nav className="hidden gap-4 text-sm text-muted-foreground md:flex">
            <Link href="/dashboard" className="hover:text-foreground">Dashboard</Link>
            <Link href="/projetos" className="hover:text-foreground">Projetos</Link>
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="hidden text-muted-foreground sm:inline">
              {user.name} <span className="text-xs">({user.role})</span>
            </span>
            <Button variant="ghost" size="sm" onClick={logout}>
              Sair
            </Button>
          </div>
        </div>
      </header>
      <div className="container mx-auto py-8">{children}</div>
    </div>
  );
}
