import type { Metadata } from "next";
import "./globals.css";
import { LanguageProvider } from "@/lib/i18n";
import AppShell from "@/components/layout/AppShell";
import Providers from "@/providers";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ThemeProvider } from "@/components/theme-provider";
import { A11yProvider } from "@/components/a11y/a11y-provider";
import { Toaster } from "sonner";

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
    <html lang="no" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <A11yProvider>
            <Providers>
              <LanguageProvider>
                <AppShell>
                  <ErrorBoundary>{children}</ErrorBoundary>
                </AppShell>
              </LanguageProvider>
              <Toaster richColors closeButton position="top-right" />
            </Providers>
          </A11yProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
