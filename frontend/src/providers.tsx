"use client";

import { SessionProvider, useSession, signIn, signOut } from "next-auth/react";
import { useEffect, type ReactNode } from "react";
import { setApiToken } from "@/lib/api";

function AuthGate({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  setApiToken((session as { idToken?: string } | null)?.idToken);
  useEffect(() => {
    if ((session as { error?: string } | null)?.error !== "RefreshIdTokenError") return;
    if (typeof window === "undefined") return;
    // Don't ping signIn() while already on /login — signIn() defaults
    // callbackUrl=window.location.href, so on /login that produces
    // /login?callbackUrl=/login?callbackUrl=… which grows exponentially
    // each render and trips HTTP 431 (request headers too large).
    // Diagnosed in prod 2026-04-29.
    if (window.location.pathname === "/login") {
      // Clear the bad session so a fresh sign-in starts clean.
      void signOut({ redirect: false });
      return;
    }
    void signIn(undefined, { callbackUrl: "/dashboard" });
  }, [session]);
  if (status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  return <>{children}</>;
}

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <AuthGate>{children}</AuthGate>
    </SessionProvider>
  );
}
