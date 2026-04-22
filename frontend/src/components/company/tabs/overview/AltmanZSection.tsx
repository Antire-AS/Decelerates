"use client";

import type { AltmanZScore } from "@/lib/api-types";
import { Section } from "./shared";
import { useT } from "@/lib/i18n";
import AltmanTrendChart from "./AltmanTrendChart";
import ScenarioSlider from "./ScenarioSlider";

interface Props {
  altman: AltmanZScore;
  orgnr: string;
}

// Zone colour palette matching the broker RISK_BANDS — safe/grey/distress
// map onto Lav/Moderat/Svært høy so the Z'' panel reads consistently with
// the rule-based score above it.
const ZONE_STYLE: Record<AltmanZScore["zone"], { label: string; badge: string; bar: string }> = {
  safe:     { label: "Trygg sone",   badge: "bg-green-100 text-green-800 border-green-300",  bar: "bg-green-500" },
  grey:     { label: "Gråsone",      badge: "bg-yellow-100 text-yellow-800 border-yellow-300", bar: "bg-yellow-500" },
  distress: { label: "Nødsone",      badge: "bg-red-100 text-red-800 border-red-300",       bar: "bg-red-500" },
};

// Altman 2000 zone thresholds — duplicated here intentionally so the UI
// can position the Z-value on a sensible 0-4 bar without a backend call.
const Z_MIN = 0;
const Z_MAX = 4;

// Human-readable meaning of each Z'' factor. Kept separate from the API
// payload so translations stay in the UI layer.
const COMPONENT_META: Array<{
  key: keyof AltmanZScore["components"];
  label: string;
  hint: string;
}> = [
  { key: "working_capital_ratio",   label: "Likviditet",    hint: "Arbeidskapital / totale eiendeler — kortsiktig handlingsrom" },
  { key: "retained_earnings_ratio", label: "Historisk inntjening", hint: "Opptjent egenkapital / totale eiendeler — akkumulert lønnsomhet" },
  { key: "ebit_ratio",              label: "Driftslønnsomhet",     hint: "Driftsresultat / totale eiendeler — avkastning på balansen" },
  { key: "equity_to_liab_ratio",    label: "Soliditet",            hint: "Egenkapital / total gjeld — gjeldsbetjeningsevne" },
];

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

export default function AltmanZSection({ altman, orgnr }: Props) {
  const T = useT();
  const style = ZONE_STYLE[altman.zone];
  const barPercent = clamp(((altman.z_score - Z_MIN) / (Z_MAX - Z_MIN)) * 100, 0, 100);

  return (
    <Section title={T("Bankruptcy-prediksjon (Altman Z″)")}>
      <div className="flex items-center gap-3 mb-2">
        <span
          className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium ${style.badge}`}
        >
          {T(style.label)}
        </span>
        <div>
          <span className="text-xl font-bold text-foreground">{altman.z_score.toFixed(2)}</span>
          <span className="text-xs text-muted-foreground ml-1">Z″</span>
        </div>
      </div>

      {/* Z'' position indicator — 0 to 4 scale with Altman zone markers at 1.10 and 2.60 */}
      <div className="relative h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={`absolute top-0 h-full ${style.bar} rounded-full transition-all`}
          style={{ width: `${barPercent}%` }}
        />
        {/* zone boundary marks */}
        <div className="absolute top-0 h-full w-px bg-foreground/40" style={{ left: `${(1.10 / Z_MAX) * 100}%` }} />
        <div className="absolute top-0 h-full w-px bg-foreground/40" style={{ left: `${(2.60 / Z_MAX) * 100}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
        <span>0</span>
        <span className="text-red-600">1.10</span>
        <span className="text-yellow-700">2.60</span>
        <span>4+</span>
      </div>

      <div className="mt-3 space-y-1">
        {COMPONENT_META.map((c) => {
          const value = altman.components[c.key];
          return (
            <div key={c.key} className="text-xs">
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-muted-foreground" title={T(c.hint)}>
                  {T(c.label)}
                </span>
                <span className={value < 0 ? "text-red-600 font-medium" : "text-foreground font-medium"}>
                  {value.toFixed(3)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-[11px] text-muted-foreground leading-snug">
        {T("Altman Z'' kombinerer 4 finansielle forhold til en bankruptcy-sannsynlighet validert mot tusenvis av konkurser.")}{" "}
        <span className="opacity-60">{altman.formula}</span>
      </p>

      <AltmanTrendChart orgnr={orgnr} />
      <ScenarioSlider baseline={altman} />
    </Section>
  );
}
