"use client";

import { SessionProvider } from "next-auth/react";
import { type ReactNode } from "react";

// Auth disabled — AuthGate is bypassed. Pages render immediately without a session.
// To re-enable, restore the useSession / setApiToken logic below.
//
// import { useSession, signIn } from "next-auth/react";
// import { useEffect } from "react";
// import { setApiToken } from "@/lib/api";
//
// function AuthGate({ children }: { children: ReactNode }) {
//   const { data: session, status } = useSession();
//   setApiToken((session as { idToken?: string } | null)?.idToken);
//   useEffect(() => {
//     if ((session as { error?: string } | null)?.error === "RefreshIdTokenError") {
//       void signIn("azure-ad");
//     }
//   }, [session]);
//   if (status === "loading") {
//     return (
//       <div className="flex items-center justify-center min-h-screen">
//         <div className="w-5 h-5 border-2 border-[#4A6FA5] border-t-transparent rounded-full animate-spin" />
//       </div>
//     );
//   }
//   return <>{children}</>;
// }

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      {children}
    </SessionProvider>
  );
}
