"use client";

import { Fragment } from "react";
import dynamic from "next/dynamic";
import { ExternalLink, AlertTriangle, Shield, Users, TrendingUp } from "lucide-react";
import RiskBadge from "@/components/company/RiskBadge";

const CompanyMap = dynamic(() => import("@/components/company/CompanyMap"), { ssr: false });

function fmt(v: unknown): string {
  if (v == null) return "–";
  if (typeof v === "number")
    return new Intl.NumberFormat("nb-NO").format(v);
  return String(v);
}

function fmtMnok(v: unknown): string {
  if (v == null || v === "") return "–";
  const n = Number(v);
  if (isNaN(n)) return "–";
  return `${(n / 1_000_000).toLocaleString("nb-NO", { maximumFractionDigits: 1 })} MNOK`;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="broker-card space-y-3">
      <h3 className="text-sm font-semibold text-[#2C3E50]">{title}</h3>
      {children}
    </div>
  );
}

function KV({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="flex justify-between text-sm gap-4">
      <span className="text-[#8A7F74]">{label}</span>
      <span className="text-[#2C3E50] font-medium text-right">{fmt(value)}</span>
    </div>
  );
}

interface OverviewTabProps {
  org: Record<string, unknown>;
  regn: Record<string, unknown>;
  risk: {
    score?: number;
    reasons?: string[];
    equity_ratio?: number;
  };
  pep: Record<string, unknown>;
  koordinaterData: unknown;
  roles: Record<string, unknown> | null | undefined;
  licenses: Record<string, unknown> | null | undefined;
  bankruptcy: Record<string, unknown> | null | undefined;
  benchmark: Record<string, unknown> | null | undefined;
}

export default function OverviewTab({
  org,
  regn,
  risk,
  pep,
  koordinaterData,
  roles,
  licenses,
  bankruptcy,
  benchmark,
}: OverviewTabProps) {
  return (
    <div className="space-y-4">
      <Section title="Selskapsinfo">
        <KV label="Orgnr"     value={org.orgnr} />
        <KV label="Adresse"   value={org.forretningsadresse} />
        <KV label="Kommune"   value={org.kommune} />
        <KV label="Stiftet"   value={org.stiftelsesdato} />
        <KV label="Ansatte"   value={org.antallAnsatte} />
        {!!org.hjemmeside && (
          <div className="flex justify-between text-sm">
            <span className="text-[#8A7F74]">Nettsted</span>
            <a
              href={String(org.hjemmeside)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#4A6FA5] flex items-center gap-1 hover:underline"
            >
              {String(org.hjemmeside).replace(/^https?:\/\//, "").slice(0, 30)}
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        )}
      </Section>

      {/* Map */}
      {(() => {
        const coords = (koordinaterData as { coordinates?: { lat: number; lon: number } } | null)?.coordinates;
        return coords?.lat && coords?.lon ? (
          <Section title="Lokasjon">
            <CompanyMap lat={coords.lat} lon={coords.lon} label={String(org.navn ?? org.orgnr)} />
          </Section>
        ) : null;
      })()}

      <Section title="Risikoscore">
        <div className="flex items-center gap-3">
          <RiskBadge score={risk.score as number | undefined} className="text-sm px-3 py-1" />
          <span className="text-2xl font-bold text-[#2C3E50]">
            {risk.score ?? "–"}
            <span className="text-sm font-normal text-[#8A7F74]"> / 20</span>
          </span>
        </div>
        {Array.isArray(risk.reasons) && risk.reasons.length > 0 && (
          <ul className="space-y-1 mt-2">
            {(risk.reasons as string[]).map((r, i) => (
              <li key={i} className="text-xs text-[#8A7F74] flex gap-2">
                <span>•</span> {r}
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* Key financials summary */}
      {Object.keys(regn).length > 0 && (
        <Section title="Nøkkeltall">
          <KV label="Omsetning"    value={fmtMnok(regn.sumDriftsinntekter)} />
          <KV label="Nettoresultat" value={fmtMnok(regn.arsresultat)} />
          <KV label="Egenkapital"  value={fmtMnok(regn.sumEgenkapital)} />
          <KV label="Egenkapitalandel"
            value={risk.equity_ratio != null
              ? `${(Number(risk.equity_ratio) * 100).toFixed(1)}%`
              : "–"}
          />
        </Section>
      )}

      {/* Bankruptcy alert */}
      {!!bankruptcy && !!(bankruptcy.konkurs || bankruptcy.underAvvikling || bankruptcy.underTvangsavviklingEllerTvangsopplosning) && (
        <div className="broker-card border-l-4 border-red-500">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
            <span className="text-sm font-semibold text-red-700">
              {bankruptcy.konkurs ? "Konkurs" : bankruptcy.underAvvikling ? "Under avvikling" : "Under tvangsavvikling/tvangsoppløsning"}
            </span>
          </div>
        </div>
      )}

      {/* PEP / sanctions */}
      {pep && (Object.keys(pep).length > 0) && (
        <Section title="PEP / sanksjonssjekk">
          <div className="flex items-start gap-2 text-sm">
            <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
            <pre className="text-xs text-[#2C3E50] whitespace-pre-wrap overflow-auto max-h-40">
              {JSON.stringify(pep, null, 2)}
            </pre>
          </div>
        </Section>
      )}

      {/* Board members */}
      {Array.isArray((roles as Record<string, unknown> | null)?.roller) && ((roles as Record<string, unknown>).roller as unknown[]).length > 0 && (
        <Section title="Styremedlemmer">
          <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
            <Users className="w-3.5 h-3.5" />
            <span>Fra Brønnøysundregistrene</span>
          </div>
          <div className="space-y-2">
            {((roles as Record<string, unknown>).roller as Record<string, unknown>[]).slice(0, 8).map((r, i) => {
              const person = (r.person ?? r) as Record<string, unknown>;
              const navn = [person.fornavn, person.etternavn].filter(Boolean).join(" ") || (r.navn as string) || "–";
              const rolle = (r.rolle as Record<string, unknown>)?.beskrivelse ?? r.tittel ?? r.type ?? "";
              return (
                <div key={i} className="flex justify-between text-sm">
                  <span className="text-[#2C3E50] font-medium">{navn}</span>
                  <span className="text-[#8A7F74] text-xs">{String(rolle)}</span>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Finanstilsynet licenses */}
      {Array.isArray((licenses as Record<string, unknown> | null)?.licences) && ((licenses as Record<string, unknown>).licences as unknown[]).length > 0 && (
        <Section title="Finanstilsynet — konsesjoner">
          <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
            <Shield className="w-3.5 h-3.5" />
            <span>Registrerte finanskonsesjoner</span>
          </div>
          <div className="space-y-1.5">
            {((licenses as Record<string, unknown>).licences as Record<string, unknown>[]).slice(0, 6).map((l, i) => (
              <div key={i} className="text-xs text-[#2C3E50] flex items-start gap-1.5">
                <span className="text-[#C8A951] mt-0.5">•</span>
                <span>{String(l.type ?? l.name ?? l.licence_type ?? JSON.stringify(l))}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Industry benchmark */}
      {benchmark && Object.keys(benchmark).length > 0 && (
        <Section title="SSB-bransjesammenligning">
          <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Typiske nøkkeltall for bransjen</span>
          </div>
          {Object.entries(benchmark as Record<string, { low: number; high: number } | number | string>)
            .filter(([k]) => !["naeringskode", "beskrivelse", "source"].includes(k))
            .slice(0, 5)
            .map(([key, val]) => (
              <div key={key} className="flex justify-between text-sm">
                <span className="text-[#8A7F74] capitalize">{key.replace(/_/g, " ")}</span>
                <span className="text-[#2C3E50] font-medium text-xs">
                  {typeof val === "object" && val !== null && "low" in val
                    ? `${(val as { low: number; high: number }).low}–${(val as { low: number; high: number }).high}%`
                    : String(val)}
                </span>
              </div>
            ))}
        </Section>
      )}
    </div>
  );
}
