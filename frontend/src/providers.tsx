"use client";

import { SessionProvider, useSession } from "next-auth/react";
import { useEffect, type ReactNode } from "react";
import { setApiToken } from "@/lib/api";

/** Syncs the Entra ID token into apiFetch so every API call includes the Bearer header. */
function TokenSync() {
  const { data: session } = useSession();
  useEffect(() => {
    setApiToken((session as { idToken?: string } | null)?.idToken);
  }, [session]);
  return null;
}

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <TokenSync />
      {children}
    </SessionProvider>
  );
}
