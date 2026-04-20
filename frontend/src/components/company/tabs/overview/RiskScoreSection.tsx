"use client";

import RiskBadge from "@/components/company/RiskBadge";
import type { RiskFactor } from "@/lib/api-types";
import { Section, CATEGORY_DOTS, riskGuidanceForLabel } from "./shared";
import { useRiskConfig } from "@/lib/useRiskConfig";

interface Props {
  score?: number;
  factors: RiskFactor[];
}

export default function RiskScoreSection({ score, factors }: Props) {
  const { bandFor } = useRiskConfig();
  const band = bandFor(score);
  const guidance = riskGuidanceForLabel(band.label);
  const factorsByCategory = factors.reduce<Record<string, RiskFactor[]>>((acc, f) => {
    (acc[f.category] ??= []).push(f);
    return acc;
  }, {});

  return (
    <>
      <Section title="Risikoscore">
        <div className="flex items-center gap-3 mb-2">
          <RiskBadge score={score} />
          <div>
            <span className="text-xl font-bold text-foreground">{score ?? "–"}</span>
            <span className="text-sm text-muted-foreground ml-1">/ 20</span>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">{guidance}</p>
        {/* Gradient bar 0–20 */}
        <div className="mt-2 relative h-2 rounded-full bg-gradient-to-r from-green-400 via-yellow-400 to-red-500 overflow-hidden">
          {score != null && (
            <div
              className="absolute top-0 h-full w-1 bg-primary rounded-full"
              style={{ left: `${Math.min(score / 20 * 100, 100)}%` }}
            />
          )}
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
          <span>0 Lav</span><span>10 Moderat</span><span>20 Svært høy</span>
        </div>
      </Section>

      {factors.length > 0 && (
        <Section title="Risikofaktorer">
          {Object.entries(factorsByCategory).map(([cat, items]) => (
            <div key={cat} className="mb-2 last:mb-0">
              <div className="flex items-center gap-1.5 text-xs font-medium text-foreground mb-1">
                <span className="w-2 h-2 rounded-full" style={{ background: CATEGORY_DOTS[cat] ?? "#999" }} />
                {cat}
              </div>
              {items.map((f, i) => (
                <div key={i} className="flex justify-between items-baseline text-xs ml-3.5 gap-2">
                  <span className="text-muted-foreground">{f.label}</span>
                  <span className="text-foreground font-medium">+{f.points}</span>
                </div>
              ))}
            </div>
          ))}
        </Section>
      )}
    </>
  );
}
