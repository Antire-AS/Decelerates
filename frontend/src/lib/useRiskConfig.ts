import useSWR from "swr";
import { getRiskConfig, type RiskBand } from "./api";

// Mirrors api/risk.py::RISK_BANDS — keep these two in sync. The hook
// prefers the live /risk/config response; this constant is only used
// before the first response or if the endpoint is unreachable.
export const FALLBACK_RISK_BANDS: readonly RiskBand[] = [
  { label: "Lav",        min: 0,  max: 5,  color: "#27AE60" },
  { label: "Moderat",    min: 6,  max: 10, color: "#C8A951" },
  { label: "Høy",        min: 11, max: 15, color: "#E67E22" },
  { label: "Svært høy",  min: 16, max: 20, color: "#C0392B" },
] as const;

export const UNKNOWN_BAND: RiskBand = {
  label: "Ukjent", min: -1, max: -1, color: "#C4BDB4",
};

/**
 * Tailwind class lookup for band-tinted backgrounds (e.g., risk score
 * pills in Portal, PortfolioTab, CompareTab). Centralised here so the
 * mapping cannot drift between consumers.
 */
const BAND_TAILWIND_BG: Record<string, string> = {
  "Lav":       "bg-green-100 text-green-700",
  "Moderat":   "bg-amber-100 text-amber-700",
  "Høy":       "bg-red-100 text-red-700",
  "Svært høy": "bg-red-100 text-red-700",
  "Ukjent":    "bg-gray-100 text-gray-700",
};

export function bandTailwindClass(label: string): string {
  return BAND_TAILWIND_BG[label] ?? BAND_TAILWIND_BG["Ukjent"];
}

const FALLBACK_MAX_SCORE = 20;

export interface UseRiskConfigResult {
  bands: readonly RiskBand[];
  maxScore: number;
  /** Returns the band a score falls into, or UNKNOWN_BAND if score is null/undefined. */
  bandFor: (score?: number | null) => RiskBand;
  /** Index in `bands` for the score, or `bands.length` for unknown. */
  bandIndexFor: (score?: number | null) => number;
}

export function useRiskConfig(): UseRiskConfigResult {
  const { data } = useSWR("risk-config", getRiskConfig, {
    revalidateOnFocus: false,
    revalidateIfStale: false,
    dedupingInterval: 60_000,
  });
  const bands = data?.bands ?? FALLBACK_RISK_BANDS;
  const maxScore = data?.max_score ?? FALLBACK_MAX_SCORE;

  const bandFor = (score?: number | null): RiskBand => {
    if (score == null) return UNKNOWN_BAND;
    for (const b of bands) {
      if (score >= b.min && score <= b.max) return b;
    }
    return bands[bands.length - 1];
  };

  const bandIndexFor = (score?: number | null): number => {
    if (score == null) return bands.length;
    for (let i = 0; i < bands.length; i++) {
      if (score >= bands[i].min && score <= bands[i].max) return i;
    }
    return bands.length - 1;
  };

  return { bands, maxScore, bandFor, bandIndexFor };
}
