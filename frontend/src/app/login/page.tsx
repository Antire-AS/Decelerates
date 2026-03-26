"use client";

import { signIn } from "next-auth/react";
import { Scale } from "lucide-react";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-[#F5F0EB] flex items-center justify-center">
      <div className="broker-card w-full max-w-sm text-center space-y-6">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2">
          <Scale className="w-8 h-8 text-[#4A6FA5]" />
          <div className="text-left">
            <p className="text-lg font-bold text-[#2C3E50] leading-tight">Broker</p>
            <p className="text-sm text-[#8A7F74] leading-tight">Accelerator</p>
          </div>
        </div>

        <div>
          <h1 className="text-xl font-bold text-[#2C3E50]">Logg inn</h1>
          <p className="text-sm text-[#8A7F74] mt-1">
            Forsikringsmegling · Due Diligence · Risikoprofil
          </p>
        </div>

        <button
          onClick={() => signIn("azure-ad", { callbackUrl: "/dashboard" })}
          className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166] transition-colors"
        >
          {/* Microsoft logo */}
          <svg width="18" height="18" viewBox="0 0 21 21" fill="none">
            <rect x="1"  y="1"  width="9" height="9" fill="#F25022" />
            <rect x="11" y="1"  width="9" height="9" fill="#7FBA00" />
            <rect x="1"  y="11" width="9" height="9" fill="#00A4EF" />
            <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
          </svg>
          Logg inn med Microsoft
        </button>

        <p className="text-xs text-[#C4BDB4]">
          Kun for autoriserte meglere
        </p>
      </div>
    </div>
  );
}
