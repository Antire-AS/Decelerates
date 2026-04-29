"use client";

import { AlertTriangle, ShieldCheck, ShieldAlert } from "lucide-react";
import { useT } from "@/lib/i18n";
import { useRiskConfig, bandTailwindClass } from "@/lib/useRiskConfig";

interface RiskFactor {
  label: string;
  points: number;
  category?: string;
  detail?: string;
}

interface PepHit {
  id?: string;
  name?: string;
  schema?: string;
  datasets?: string[];
  topics?: string[];
}

interface Props {
  risk: {
    score?: number | null;
    factors?: RiskFactor[];
    reasons?: string[];
  };
  pep: {
    hit_count?: number;
    hits?: PepHit[];
    query?: string;
  };
}

function severityBadgeFor(points: number): string {
  if (points >= 4) return "bg-red-100 text-red-700";
  if (points >= 2) return "bg-amber-100 text-amber-700";
  return "bg-muted text-muted-foreground";
}

export default function RiskPepTab({ risk, pep }: Props) {
  const T = useT();
  const { bandFor, maxScore } = useRiskConfig();

  const factors: RiskFactor[] = risk.factors ?? [];
  const score = typeof risk.score === "number" ? risk.score : null;
  const band = score != null ? bandFor(score) : null;
  const hits: PepHit[] = pep.hits ?? [];

  return (
    <div className="space-y-5">
      {/* Risikofaktorer card */}
      <div className="broker-card">
        <div className="flex items-start justify-between mb-3">
          <h2 className="text-sm font-semibold text-foreground">
            {T("Risikofaktorer")}
          </h2>
          {score != null && band && (
            <span className={`inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-full ${bandTailwindClass(band.label)}`}>
              {T("Total score")} {score}/{maxScore} · {T(band.label)}
            </span>
          )}
        </div>

        {factors.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {T("Ingen risikofaktorer registrert.")}
          </p>
        ) : (
          <div className="space-y-2">
            {factors.map((f, i) => {
              const sev = severityBadgeFor(f.points);
              const sevLabel = f.points >= 4 ? "Høy" : f.points >= 2 ? "Moderat" : "Lav";
              return (
                <div
                  key={`${f.label}-${i}`}
                  className="flex items-start gap-3 p-3 rounded-md bg-muted/40"
                >
                  <span className="inline-flex items-center justify-center w-9 h-7 rounded text-xs font-bold bg-background border border-border text-foreground shrink-0">
                    +{f.points}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground">{f.label}</p>
                    {f.detail && (
                      <p className="text-xs text-muted-foreground mt-0.5">{f.detail}</p>
                    )}
                    {f.category && (
                      <p className="text-[10px] uppercase tracking-wide text-muted-foreground mt-1">
                        {f.category}
                      </p>
                    )}
                  </div>
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${sev} shrink-0`}>
                    {T(sevLabel)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* PEP- og sanksjonsscreening card */}
      <div className="broker-card">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              {T("PEP- og sanksjonsscreening")}
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {T("OpenSanctions · 100+ lister inkl. UN, EU, OFAC")}
            </p>
          </div>
          {hits.length > 0 ? (
            <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-amber-100 text-amber-800">
              <AlertTriangle className="w-3 h-3" />
              {hits.length} {T("treff")}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700">
              <ShieldCheck className="w-3 h-3" />
              {T("Ingen treff")}
            </span>
          )}
        </div>

        {hits.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {T("Ingen styremedlemmer eller selskap har PEP-treff.")}
          </p>
        ) : (
          <>
            <div className="flex items-start gap-2 p-3 rounded-md bg-amber-50 border border-amber-200 mb-3">
              <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-xs text-amber-800">
                {hits.length} {T("treff registrert. Anbefales gjennomgang før KYC-godkjenning og signering.")}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted-foreground border-b border-border">
                    <th className="text-left pb-2 font-medium">{T("Navn")}</th>
                    <th className="text-left pb-2 font-medium">{T("Type")}</th>
                    <th className="text-left pb-2 font-medium">{T("Lister")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {hits.map((h, i) => (
                    <tr key={h.id ?? `hit-${i}`}>
                      <td className="py-2 font-medium text-foreground">{h.name ?? "—"}</td>
                      <td className="py-2 text-xs text-muted-foreground">{h.schema ?? "—"}</td>
                      <td className="py-2 text-xs text-muted-foreground">
                        {(h.datasets ?? []).slice(0, 3).join(", ") || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
