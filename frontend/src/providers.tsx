"use client";

import { SessionProvider, useSession, signIn } from "next-auth/react";
import { useEffect, type ReactNode } from "react";
import { setApiToken } from "@/lib/api";

/**
 * Sets the auth token synchronously during render (before children mount) and
 * holds rendering until the session is resolved so SWR calls never fire without
 * a token. If the background token refresh fails, triggers a re-login.
 */
function AuthGate({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();

  // Set synchronously during render — by the time children mount the token is ready.
  setApiToken((session as { idToken?: string } | null)?.idToken);

  // If the silent id_token refresh failed, force the user to re-authenticate.
  useEffect(() => {
    if ((session as { error?: string } | null)?.error === "RefreshIdTokenError") {
      void signIn("azure-ad");
    }
  }, [session]);

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-5 h-5 border-2 border-[#4A6FA5] border-t-transparent rounded-full animate-spin" />
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
