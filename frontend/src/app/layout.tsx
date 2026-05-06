import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Jump GP Portal",
  description: "Sistema de Report e Gestão Estratégica de Projetos da Jump Label",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">{children}</body>
    </html>
  );
}
