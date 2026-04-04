import type { Metadata } from "next";
import "./globals.css";
import { LanguageProvider } from "@/lib/i18n";
import AppShell from "@/components/layout/AppShell";
import Providers from "@/providers";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata: Metadata = {
  title: "Broker Accelerator",
  description: "Forsikringsmegling · Due Diligence · Risikoprofil",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="no">
      <body>
        <Providers>
          <LanguageProvider>
            <AppShell>
              <ErrorBoundary>{children}</ErrorBoundary>
            </AppShell>
          </LanguageProvider>
        </Providers>
      </body>
    </html>
  );
}
