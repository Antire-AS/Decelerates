// Auth disabled — redirect straight to the app.
// To re-enable login: remove the redirect import/call below and uncomment the login UI block.

import { redirect } from "next/navigation";

export default function LoginPage() {
  // TODO: re-enable when brokers are ready to log in
  redirect("/dashboard");

  // ── Login UI (disabled) ───────────────────────────────────────────────────
  // "use client";
  // import { signIn } from "next-auth/react";
  // import { Scale } from "lucide-react";
  //
  // return (
  //   <div className="min-h-screen bg-background flex items-center justify-center">
  //     <div className="broker-card w-full max-w-sm text-center space-y-6">
  //       <div className="flex items-center justify-center gap-2">
  //         <Scale className="w-8 h-8 text-primary" />
  //         <div className="text-left">
  //           <p className="text-lg font-bold text-foreground leading-tight">Broker</p>
  //           <p className="text-sm text-muted-foreground leading-tight">Accelerator</p>
  //         </div>
  //       </div>
  //       <div>
  //         <h1 className="text-xl font-bold text-foreground">Logg inn</h1>
  //         <p className="text-sm text-muted-foreground mt-1">
  //           Forsikringsmegling · Due Diligence · Risikoprofil
  //         </p>
  //       </div>
  //       <button
  //         onClick={() => signIn("azure-ad", { callbackUrl: "/dashboard" })}
  //         className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
  //       >
  //         <svg width="18" height="18" viewBox="0 0 21 21" fill="none">
  //           <rect x="1"  y="1"  width="9" height="9" fill="#F25022" />
  //           <rect x="11" y="1"  width="9" height="9" fill="#7FBA00" />
  //           <rect x="1"  y="11" width="9" height="9" fill="#00A4EF" />
  //           <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
  //         </svg>
  //         Logg inn med Microsoft
  //       </button>
  //       <p className="text-xs text-muted-foreground">Kun for autoriserte meglere</p>
  //     </div>
  //   </div>
  // );
}
