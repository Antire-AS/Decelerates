"use client";

import useSWR from "swr";
import { getInsuranceBenchmarks, type PremiumEstimate } from "@/lib/api";
import { fmtNok } from "@/lib/format";
import { TrendingUp, Info } from "lucide-react";

interface Props {
  revenue?: number | null;
  naceSection?: string | null;
}

export default function PremiumBenchmark({ revenue, naceSection }: Props) {
  const nace = naceSection?.charAt(0)?.toUpperCase() || undefined;
  const { data } = useSWR(
    revenue ? `benchmark-${revenue}-${nace}` : null,
    () => getInsuranceBenchmarks(revenue ?? undefined, nace),
  );

  if (!data?.estimates) return null;

  const estimates = Object.entries(data.estimates) as [string, PremiumEstimate][];
  const firstEstimate = estimates[0]?.[1];

  return (
    <div className="broker-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-bold text-foreground flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-primary" />
          Typiske premier
        </h3>
        {firstEstimate && (
          <span className="text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-full">
            {firstEstimate.bracket_label}
            {firstEstimate.nace_adjustment !== 1.0 && (
              <span className="ml-1">
                · NACE {nace} ({firstEstimate.nace_adjustment > 1 ? "+" : ""}
                {Math.round((firstEstimate.nace_adjustment - 1) * 100)}%)
              </span>
            )}
          </span>
        )}
      </div>

      <p className="text-xs text-muted-foreground mb-4 flex items-start gap-1.5">
        <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
        Indikative årspremier basert på bedriftsstørrelse og bransje. Ikke tilbud — veiledende markedsnivå.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {estimates.map(([key, est]) => (
          <div
            key={key}
            className="p-3 rounded-lg border border-border hover:border-primary transition-colors"
          >
            <div className="text-sm font-semibold text-foreground mb-0.5">{est.label}</div>
            <div className="text-xs text-muted-foreground mb-2 line-clamp-2">{est.description}</div>
            <div className="flex items-baseline gap-1">
              <span className="text-xs text-muted-foreground">{fmtNok(est.low)}</span>
              <span className="text-xs text-muted-foreground">–</span>
              <span className="text-base font-bold text-foreground">{fmtNok(est.mid)}</span>
              <span className="text-xs text-muted-foreground">–</span>
              <span className="text-xs text-muted-foreground">{fmtNok(est.high)}</span>
            </div>
            <div className="mt-1.5 h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full"
                style={{ width: `${Math.min(100, (est.mid / est.high) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
