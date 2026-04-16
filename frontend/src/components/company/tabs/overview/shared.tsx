import React from "react";
import { fmt } from "@/lib/format";

export const CATEGORY_DOTS: Record<string, string> = {
  Selskapsstatus: "#C0392B",
  "Økonomi": "#E67E22",
  Bransje: "#C8A951",
  Historikk: "#4A6FA5",
  Eksponering: "#8E44AD",
};

export function riskBandLabel(score?: number): { label: string; guidance: string } {
  if (score == null) return { label: "Ukjent", guidance: "Score ikke beregnet." };
  if (score <= 5) return { label: "Lav", guidance: "Normalpremie forventes. Godt grunnlag for tegning." };
  if (score <= 10) return { label: "Moderat", guidance: "Forvent normal til lett forhøyet premie. Standard tegning." };
  if (score <= 15) return { label: "Høy", guidance: "Forhøyet premie sannsynlig. Krever ekstra dokumentasjon." };
  return { label: "Svært høy", guidance: "Tegning kan være vanskelig. Vurder spesialmarked." };
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
