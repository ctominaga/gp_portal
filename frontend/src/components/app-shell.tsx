"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { NotificationBell } from "@/components/notification-bell";
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

  const navByRole = (() => {
    if (user.role === "PMO" || user.role === "OPERATOR") {
      const items = [
        { href: "/pmo/portfolio", label: "Portfólio" },
        { href: "/projetos", label: "Projetos" },
        { href: "/pmo/scope-changes", label: "Transições" },
      ];
      // F5.7 — link admin LGPD só para PMO (OPERATOR não tem acesso ao
      // RBAC do backend; mostrar o link seria 403 no clique).
      if (user.role === "PMO") {
        items.push({ href: "/admin/data-requests", label: "LGPD" });
      }
      return items;
    }
    if (user.role === "CLIENT") {
      return [{ href: "/portal", label: "Meus projetos" }];
    }
    return [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/projetos", label: "Projetos" },
    ];
  })();

  const home = user.role === "CLIENT" ? "/portal" : user.role === "PMO" ? "/pmo/portfolio" : "/dashboard";

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
        <div className="container mx-auto flex h-14 items-center gap-6">
          <Link href={home} className="font-semibold tracking-tight">
            Jump GP Portal
          </Link>
          <nav className="hidden gap-4 text-sm text-muted-foreground md:flex">
            {navByRole.map((n) => (
              <Link key={n.href} href={n.href} className="hover:text-foreground">
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <NotificationBell />
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
