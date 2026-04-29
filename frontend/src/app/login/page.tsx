"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Scale } from "lucide-react";

function LoginContent() {
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") ?? "/dashboard";

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="broker-card w-full max-w-sm text-center space-y-6">
        <div className="flex items-center justify-center gap-2">
          <Scale className="w-8 h-8 text-primary" />
          <div className="text-left">
            <p className="text-lg font-bold text-foreground leading-tight">Broker</p>
            <p className="text-sm text-muted-foreground leading-tight">Accelerator</p>
          </div>
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">Logg inn</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Forsikringsmegling · Due Diligence · Risikoprofil
          </p>
        </div>
        <div className="space-y-3">
          <button
            onClick={() => signIn("google", { callbackUrl })}
            className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg bg-white border border-border text-foreground text-sm font-medium hover:bg-muted transition-colors"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" />
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.583-5.036-3.71H.957v2.332A8.997 8.997 0 0 0 9 18z" />
              <path fill="#FBBC05" d="M3.964 10.708A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.708V4.96H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.04l3.007-2.332z" />
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.96L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" />
            </svg>
            Logg inn med Google
          </button>
          <button
            onClick={() => signIn("azure-ad", { callbackUrl })}
            className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <svg width="18" height="18" viewBox="0 0 21 21" fill="none" aria-hidden="true">
              <rect x="1" y="1" width="9" height="9" fill="#F25022" />
              <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
              <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
              <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
            </svg>
            Logg inn med Microsoft
          </button>
        </div>
        <p className="text-xs text-muted-foreground">Kun for autoriserte meglere</p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  );
}
