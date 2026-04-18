import React from "react";
import { fmt } from "@/lib/format";

export const CATEGORY_DOTS: Record<string, string> = {
  Selskapsstatus: "#C0392B",
  "Økonomi": "#E67E22",
  Bransje: "#C8A951",
  Historikk: "#4A6FA5",
  Eksponering: "#8E44AD",
};

const GUIDANCE_BY_LABEL: Record<string, string> = {
  "Lav":       "Normalpremie forventes. Godt grunnlag for tegning.",
  "Moderat":   "Forvent normal til lett forhøyet premie. Standard tegning.",
  "Høy":       "Forhøyet premie sannsynlig. Krever ekstra dokumentasjon.",
  "Svært høy": "Tegning kan være vanskelig. Vurder spesialmarked.",
  "Ukjent":    "Score ikke beregnet.",
};

/**
 * Synchronous helper used by callers that already have a band label in hand
 * (e.g., from `useRiskConfig().bandFor(score)`). Returns the broker-facing
 * guidance copy for that band.
 */
export function riskGuidanceForLabel(label: string): string {
  return GUIDANCE_BY_LABEL[label] ?? GUIDANCE_BY_LABEL["Ukjent"];
}

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="broker-card space-y-3">
      <h3 className="text-sm font-semibold text-[#2C3E50]">{title}</h3>
      {children}
    </div>
  );
}

export function KV({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="flex justify-between text-sm gap-4">
      <span className="text-[#8A7F74]">{label}</span>
      <span className="text-[#2C3E50] font-medium text-right">{fmt(value)}</span>
    </div>
  );
}
