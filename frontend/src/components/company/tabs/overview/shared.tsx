import React, { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
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

/**
 * Section card with optional collapse-and-remember behaviour.
 *
 * When `collapsibleId` is set, the header becomes a toggle button and the
 * collapsed/expanded state is persisted to `localStorage` under that key.
 * Use a stable, user-scoped key like `overview-<orgnr>-selskap` so per-company
 * preferences don't bleed across companies.
 *
 * Without `collapsibleId` the section is a plain card (current behaviour).
 */
export function Section({
  title,
  children,
  collapsibleId,
  defaultCollapsed = false,
}: {
  title: string;
  children: React.ReactNode;
  collapsibleId?: string;
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState<boolean>(defaultCollapsed);
  const [hydrated, setHydrated] = useState(!collapsibleId);

  useEffect(() => {
    if (!collapsibleId) return;
    try {
      const stored = localStorage.getItem(`section-collapsed:${collapsibleId}`);
      if (stored !== null) setCollapsed(stored === "1");
    } catch {
      /* no-op — localStorage can throw in private mode */
    }
    setHydrated(true);
  }, [collapsibleId]);

  function toggle() {
    if (!collapsibleId) return;
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem(`section-collapsed:${collapsibleId}`, next ? "1" : "0");
    } catch {
      /* no-op */
    }
  }

  if (!collapsibleId) {
    return (
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {children}
      </div>
    );
  }

  // Skip render until localStorage read completes so SSR/CSR don't flash.
  if (!hydrated) {
    return (
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
    );
  }

  return (
    <div className="broker-card space-y-3">
      <button
        type="button"
        onClick={toggle}
        className="w-full flex items-center justify-between gap-2 text-left -mx-1 px-1 py-0.5 rounded hover:bg-muted/50 transition-colors"
        aria-expanded={!collapsed}
      >
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <ChevronDown
          className={`w-4 h-4 text-muted-foreground shrink-0 transition-transform ${
            collapsed ? "-rotate-90" : ""
          }`}
        />
      </button>
      {!collapsed && <div className="space-y-3">{children}</div>}
    </div>
  );
}

export function KV({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="flex justify-between text-sm gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-foreground font-medium text-right">{fmt(value)}</span>
    </div>
  );
}
