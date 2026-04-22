"use client";

import { useMemo, useState } from "react";
import type { AltmanZScore } from "@/lib/api-types";
import { applyScenario, recompute, type AltmanComponents } from "@/lib/altman";
import { useT } from "@/lib/i18n";

interface Props {
  baseline: AltmanZScore;
}

// Range ±50% for EBIT (operating shock), ±30% for equity (capital event).
// Coarser sliders beat that — broker conversations care about "down 20%"
// not "down 17.4%".
const EBIT_RANGE = 0.5;
const EQUITY_RANGE = 0.3;
const STEP = 0.05;

const ZONE_STYLE: Record<AltmanZScore["zone"], { label: string; text: string; bg: string }> = {
  safe: { label: "Trygg sone", text: "text-green-800", bg: "bg-green-100" },
  grey: { label: "Gråsone", text: "text-yellow-800", bg: "bg-yellow-100" },
  distress: { label: "Nødsone", text: "text-red-800", bg: "bg-red-100" },
};

function fmtPct(delta: number): string {
  const sign = delta > 0 ? "+" : "";
  return `${sign}${Math.round(delta * 100)}%`;
}

export default function ScenarioSlider({ baseline }: Props) {
  const T = useT();
  const [ebitDelta, setEbitDelta] = useState(0);
  const [equityDelta, setEquityDelta] = useState(0);

  // The component ratios the backend returned ARE the x1-x4 values. The
  // scenario function just scales them — no reconstitution of absolute NOK
  // amounts needed.
  const baseComponents: AltmanComponents = baseline.components;

  const scenario = useMemo(
    () => recompute(applyScenario(baseComponents, ebitDelta, equityDelta)),
    [baseComponents, ebitDelta, equityDelta],
  );

  const delta = scenario.z_score - baseline.z_score;
  const deltaSign = delta > 0 ? "+" : "";
  const deltaColor =
    delta > 0 ? "text-green-600" : delta < 0 ? "text-red-600" : "text-muted-foreground";

  const zoneChange = scenario.zone !== baseline.zone;
  const scenarioStyle = ZONE_STYLE[scenario.zone];

  function reset(): void {
    setEbitDelta(0);
    setEquityDelta(0);
  }

  return (
    <div className="mt-4 pt-3 border-t border-muted">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-semibold text-foreground">
          {T("Scenario-simulator")}
        </h4>
        {(ebitDelta !== 0 || equityDelta !== 0) && (
          <button
            onClick={reset}
            className="text-[10px] text-primary hover:underline"
          >
            {T("Tilbakestill")}
          </button>
        )}
      </div>

      <div className="space-y-3">
        <div>
          <div className="flex justify-between text-[11px] text-muted-foreground mb-0.5">
            <span>{T("Driftsresultat-sjokk")}</span>
            <span className="font-medium text-foreground">{fmtPct(ebitDelta)}</span>
          </div>
          <input
            type="range"
            min={-EBIT_RANGE}
            max={EBIT_RANGE}
            step={STEP}
            value={ebitDelta}
            onChange={(e) => setEbitDelta(parseFloat(e.target.value))}
            className="w-full accent-primary cursor-pointer"
            aria-label={T("Driftsresultat-sjokk")}
          />
        </div>
        <div>
          <div className="flex justify-between text-[11px] text-muted-foreground mb-0.5">
            <span>{T("Egenkapital-sjokk")}</span>
            <span className="font-medium text-foreground">{fmtPct(equityDelta)}</span>
          </div>
          <input
            type="range"
            min={-EQUITY_RANGE}
            max={EQUITY_RANGE}
            step={STEP}
            value={equityDelta}
            onChange={(e) => setEquityDelta(parseFloat(e.target.value))}
            className="w-full accent-primary cursor-pointer"
            aria-label={T("Egenkapital-sjokk")}
          />
        </div>
      </div>

      {/* Scenario result */}
      <div className="mt-3 flex items-center justify-between p-2 rounded-md bg-muted/50">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-medium ${scenarioStyle.bg} ${scenarioStyle.text}`}
          >
            {T(scenarioStyle.label)}
          </span>
          <div>
            <span className="text-base font-bold text-foreground">
              {scenario.z_score.toFixed(2)}
            </span>
            <span className="text-[10px] text-muted-foreground ml-1">Z″</span>
          </div>
        </div>
        <div className={`text-xs font-semibold ${deltaColor}`}>
          {deltaSign}
          {delta.toFixed(2)}
          {zoneChange && (
            <span className="ml-1 text-[10px] opacity-75">
              ({T(ZONE_STYLE[baseline.zone].label)} → {T(scenarioStyle.label)})
            </span>
          )}
        </div>
      </div>

      <p className="mt-2 text-[10px] text-muted-foreground leading-snug">
        {T(
          "Dra for å simulere resultat- eller kapital-sjokk. Tallet er en ren matematisk prognose — ingen markeds- eller operasjonsmodell.",
        )}
      </p>
    </div>
  );
}
