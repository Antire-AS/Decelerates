"use client";

import dynamic from "next/dynamic";
import useSWR from "swr";
import { ExternalLink, AlertTriangle, TrendingUp, BarChart3 } from "lucide-react";
import type { HistoryRow, RiskFactor } from "@/lib/api-types";
import type {
  BankruptcyOut,
  BoardMembersOut,
  LicensesOut,
  StrukturOut,
  BenchmarkOut,
  KoordinaterOut,
} from "@/lib/api";
import { fmtMnok } from "@/lib/format";
import { getOrgPeerBenchmark } from "@/lib/api";
import { Section, KV } from "./overview/shared";
import RiskScoreSection from "./overview/RiskScoreSection";
import BoardSection from "./overview/BoardSection";
import LicensesSection from "./overview/LicensesSection";
import StrukturSection from "./overview/StrukturSection";

const CompanyMap = dynamic(() => import("@/components/company/CompanyMap"), { ssr: false });

interface OverviewTabProps {
  orgnr: string;
  org: Record<string, unknown>;
  regn: Record<string, unknown>;
  history?: HistoryRow[];
  risk: {
    score?: number;
    reasons?: string[];
    factors?: RiskFactor[];
    equity_ratio?: number;
  };
  pep: Record<string, unknown>;
  koordinaterData: KoordinaterOut | null | undefined;
  roles: BoardMembersOut | null | undefined;
  licenses: LicensesOut | null | undefined;
  bankruptcy: BankruptcyOut | null | undefined;
  benchmark: BenchmarkOut | null | undefined;
  struktur?: StrukturOut | null;
}

export default function OverviewTab({
  orgnr, org, regn, history, risk, pep,
  koordinaterData, roles, licenses, bankruptcy, benchmark, struktur,
}: OverviewTabProps) {
  const { data: peerData } = useSWR(`peer-${orgnr}`, () => getOrgPeerBenchmark(orgnr).catch(() => null));

  const latestRow = history?.length ? [...history].sort((a, b) => b.year - a.year)[0] : null;
  const finansData: Record<string, unknown> | null = Object.keys(regn).length > 0
    ? {
        sumDriftsinntekter: regn.sumDriftsinntekter ?? regn.sum_driftsinntekter,
        arsresultat: regn.arsresultat ?? regn.aarsresultat,
        sumEgenkapital: regn.sumEgenkapital ?? regn.sum_egenkapital,
        _year: regn._year ?? regn.regnskapsår,
      }
    : latestRow
      ? {
          sumDriftsinntekter: latestRow.revenue ?? latestRow.sumDriftsinntekter,
          arsresultat: latestRow.arsresultat,
          sumEgenkapital: latestRow.sumEgenkapital,
          _year: latestRow.year,
        }
      : null;

  const coords = (koordinaterData as { coordinates?: { lat: number; lon: number } } | null)?.coordinates;
  const bk = (bankruptcy ?? {}) as Record<string, unknown>;
  const isKonkurs = !!(bk.konkurs || bk.under_konkursbehandling);
  const isAvvikling = !!(bk.under_avvikling ?? bk.underAvvikling);
  const isBankrupt = isKonkurs || isAvvikling;
  const bankruptLabel = isKonkurs ? "Konkurs / under konkursbehandling" : isAvvikling ? "Under avvikling" : "";

  const factors = (risk.factors ?? []) as RiskFactor[];

  return (
    <div className="space-y-4">
      {/* Bankruptcy alert */}
      {isBankrupt && (
        <div className="broker-card border-l-4 border-red-500">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
            <span className="text-sm font-semibold text-red-700">{bankruptLabel}</span>
          </div>
        </div>
      )}

      {/* Top 2-column: Company info + Risk */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <div className="space-y-4">
          <Section title="Selskapsinfo">
            {Object.entries({
              "Org.nr": org.orgnr, "Org.form": org.organisasjonsform,
              "Kommune": org.kommune, "Land": org.land,
              "Bransje": org.naeringskode1_beskrivelse, "Stiftelsesdato": org.stiftelsesdato,
            }).map(([k, v]) => {
              if (!v) return null;
              return (
                <div key={k} className="flex justify-between text-sm gap-2">
                  <span className="text-[#8A7F74]">{k}</span>
                  <span className="text-[#2C3E50] font-medium text-right text-xs">{String(v)}</span>
                </div>
              );
            })}
            {!!org.hjemmeside && (
              <a href={`https://${String(org.hjemmeside).replace(/^https?:\/\//, "")}`}
                target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-[#4A6FA5] hover:underline mt-1">
                <ExternalLink className="w-3 h-3" />{String(org.hjemmeside)}
              </a>
            )}
          </Section>
          {coords && (
            <Section title="Lokasjon">
              <CompanyMap lat={coords.lat} lon={coords.lon} />
            </Section>
          )}
        </div>

        <div className="space-y-4">
          <RiskScoreSection score={risk.score} factors={factors} />
          {finansData && (
            <Section title={finansData._year ? `Nøkkeltall (${finansData._year})` : "Nøkkeltall"}>
              <KV label="Omsetning" value={finansData.sumDriftsinntekter} />
              <KV label="Resultat" value={finansData.arsresultat} />
              <KV label="Egenkapital" value={finansData.sumEgenkapital} />
            </Section>
          )}
          {pep && (() => {
            const hits = (pep as { hits?: unknown[] })?.hits ?? [];
            if (hits.length === 0) return null;
            return (
              <Section title="PEP / sanksjonssjekk">
                <p className="text-xs text-red-600 font-medium mb-1">{hits.length} treff i OpenSanctions</p>
                {(hits as Record<string, unknown>[]).slice(0, 5).map((h, i) => (
                  <div key={i} className="text-xs text-[#8A7F74] flex items-start gap-1.5">
                    <AlertTriangle className="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" />
                    <span>{String(h.name ?? h.caption ?? "Treff")}</span>
                  </div>
                ))}
              </Section>
            );
          })()}
        </div>
      </div>

      {/* Bottom 2-column: Board, Licenses, Benchmarks, Structure */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <BoardSection members={roles?.members ?? []} />
        <LicensesSection licenses={licenses} />

        {benchmark?.benchmark && Object.keys(benchmark.benchmark).length > 0 && (() => {
          const b = benchmark.benchmark as Record<string, unknown>;
          const fmtPct = (v: unknown) => `${(Number(v) * 100).toFixed(0)} %`;
          const fmtRange = (lo: unknown, hi: unknown) => `${fmtPct(lo)} – ${fmtPct(hi)}`;
          const rows: { label: string; value: string }[] = [];
          if (b.industry) rows.push({ label: "Bransje", value: String(b.industry) });
          if (b.typical_equity_ratio_min != null && b.typical_equity_ratio_max != null)
            rows.push({ label: "Typisk egenkapitalandel", value: fmtRange(b.typical_equity_ratio_min, b.typical_equity_ratio_max) });
          if (b.typical_profit_margin_min != null && b.typical_profit_margin_max != null)
            rows.push({ label: "Typisk resultatmargin", value: fmtRange(b.typical_profit_margin_min, b.typical_profit_margin_max) });
          return (
            <Section title="SSB-bransjesammenligning">
              <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
                <TrendingUp className="w-3.5 h-3.5" />
                <span>Typiske nøkkeltall for bransjen{b.live === true ? " (live SSB)" : ""}</span>
              </div>
              {rows.map((row) => (
                <div key={row.label} className="flex justify-between text-sm">
                  <span className="text-[#8A7F74]">{row.label}</span>
                  <span className="text-[#2C3E50] font-medium text-xs">{row.value}</span>
                </div>
              ))}
            </Section>
          );
        })()}

        {peerData && peerData.peer_count > 0 && (
          <Section title="Bransje-benchmark (peer-sammenligning)">
            <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
              <BarChart3 className="w-3.5 h-3.5" />
              <span>NACE {peerData.nace_section || "–"} · {peerData.peer_count} peers · {peerData.source === "db_peers" ? "database" : "SSB"}</span>
            </div>
            <div className="space-y-2">
              {(["equity_ratio", "revenue", "risk_score"] as const).map((k) => {
                const m = peerData.metrics[k];
                if (!m || (m.company == null && m.peer_avg == null)) return null;
                const label = k === "equity_ratio" ? "Egenkapitalandel" : k === "revenue" ? "Omsetning" : "Risikoscore";
                const fmtVal = (v: number | null | undefined) => {
                  if (v == null) return "–";
                  if (k === "equity_ratio") return `${(v * 100).toFixed(1)}%`;
                  if (k === "revenue") return fmtMnok(v);
                  return v.toFixed(1);
                };
                return (
                  <div key={k} className="flex justify-between items-baseline text-xs">
                    <span className="text-[#8A7F74]">{label}</span>
                    <span className="text-[#2C3E50] font-medium">
                      {fmtVal(m.company)} <span className="text-[#C4BDB4]">vs</span> <span className="text-[#8A7F74]">{fmtVal(m.peer_avg)}</span>
                      {m.percentile != null && <span className="ml-2 text-[10px] text-[#4A6FA5]">P{m.percentile}</span>}
                    </span>
                  </div>
                );
              })}
            </div>
          </Section>
        )}

        <StrukturSection struktur={struktur} />
      </div>
    </div>
  );
}
