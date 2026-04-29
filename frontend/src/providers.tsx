"use client";

import { SessionProvider, useSession, signIn } from "next-auth/react";
import { useEffect, type ReactNode } from "react";
import { setApiToken } from "@/lib/api";

function AuthGate({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  setApiToken((session as { idToken?: string } | null)?.idToken);
  useEffect(() => {
    if ((session as { error?: string } | null)?.error === "RefreshIdTokenError") {
      void signIn();
    }
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
