"use client";

import dynamic from "next/dynamic";
import useSWR from "swr";
import { ExternalLink, AlertTriangle, Shield, Users, TrendingUp, BarChart3 } from "lucide-react";
import RiskBadge from "@/components/company/RiskBadge";
import type { HistoryRow, RiskFactor } from "@/lib/api-types";
import type {
  BankruptcyOut,
  BoardMembersOut,
  BoardMember,
  LicensesOut,
  StrukturOut,
  BenchmarkOut,
  KoordinaterOut,
} from "@/lib/api";
import { fmt, fmtMnok } from "@/lib/format";
import { getOrgPeerBenchmark } from "@/lib/api";

const CompanyMap = dynamic(() => import("@/components/company/CompanyMap"), { ssr: false });

// Category colors mirror the Streamlit version (api/risk.py CATEGORY_COLORS)
const CATEGORY_DOTS: Record<string, string> = {
  Selskapsstatus: "#C0392B",
  "Økonomi":       "#E67E22",
  Bransje:        "#C8A951",
  Historikk:      "#4A6FA5",
  Eksponering:    "#8E44AD",
};

function riskBandLabel(score?: number): { label: string; guidance: string } {
  if (score == null) return { label: "Ukjent", guidance: "Score ikke beregnet." };
  if (score <= 3)  return { label: "Lav",        guidance: "Normalpremie forventes. Godt grunnlag for tegning." };
  if (score <= 7)  return { label: "Moderat",    guidance: "Forvent normal til lett forhøyet premie. Standard tegning." };
  if (score <= 12) return { label: "Høy",        guidance: "Forhøyet premie sannsynlig. Krever ekstra dokumentasjon." };
  return            { label: "Svært høy", guidance: "Tegning kan være vanskelig. Vurder spesialmarked." };
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
  orgnr,
  org,
  regn,
  history,
  risk,
  pep,
  koordinaterData,
  roles,
  licenses,
  bankruptcy,
  benchmark,
  struktur,
}: OverviewTabProps) {
  // Lazy peer benchmark — only fetched when this tab is mounted
  const { data: peerData } = useSWR(`peer-${orgnr}`, () => getOrgPeerBenchmark(orgnr).catch(() => null));
  // Fall back to most recent history row when BRREG has no financial data (e.g. banks)
  const latestRow = history && history.length > 0
    ? [...history].sort((a, b) => b.year - a.year)[0]
    : null;
  // Normalize: BRREG returns camelCase, history-fallback returns snake_case
  const finansData: Record<string, unknown> | null = Object.keys(regn).length > 0
    ? {
        sumDriftsinntekter: regn.sumDriftsinntekter ?? regn.sum_driftsinntekter,
        arsresultat:        regn.arsresultat ?? regn.aarsresultat,
        sumEgenkapital:     regn.sumEgenkapital ?? regn.sum_egenkapital,
        _year:              regn._year ?? regn.regnskapsår,
      }
    : latestRow
      ? {
          sumDriftsinntekter: latestRow.revenue ?? latestRow.sumDriftsinntekter,
          arsresultat:        latestRow.arsresultat,
          sumEgenkapital:     latestRow.sumEgenkapital,
          _year:              latestRow.year,
        }
      : null;

  const coords = (koordinaterData as { coordinates?: { lat: number; lon: number } } | null)?.coordinates;
  // Backend returns snake_case (under_avvikling, under_konkursbehandling) — fall back to camelCase aliases for safety
  const bk = (bankruptcy ?? {}) as Record<string, unknown>;
  const isKonkurs   = !!(bk.konkurs || bk.under_konkursbehandling);
  const isAvvikling = !!(bk.under_avvikling ?? bk.underAvvikling);
  const isBankrupt  = isKonkurs || isAvvikling;
  const bankruptLabel = isKonkurs ? "Konkurs / under konkursbehandling" : isAvvikling ? "Under avvikling" : "";

  const riskBand = riskBandLabel(risk.score);
  const factors = (risk.factors ?? []) as RiskFactor[];
  // Group risk factors by category for the breakdown table
  const factorsByCategory = factors.reduce<Record<string, RiskFactor[]>>((acc, f) => {
    (acc[f.category] ??= []).push(f);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {/* Bankruptcy alert — always full-width at top */}
      {isBankrupt && (
        <div className="broker-card border-l-4 border-red-500">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
            <span className="text-sm font-semibold text-red-700">{bankruptLabel}</span>
          </div>
        </div>
      )}

      {/* ── 2-column layout ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">

        {/* Left: company info + map */}
        <div className="space-y-4">
          <Section title="Selskapsinfo">
            <KV label="Orgnr"     value={org.orgnr} />
            <KV label="Adresse"   value={Array.isArray(org.adresse) ? (org.adresse as string[]).filter(Boolean).join(", ") : org.adresse} />
            <KV label="Kommune"   value={org.kommune} />
            <KV label="Stiftet"   value={org.stiftelsesdato} />
            <KV label="Ansatte"   value={regn.antall_ansatte} />
            {!!org.hjemmeside && (() => {
              // BRREG returns the website without a scheme (e.g. "www.dnb.no").
              // The browser would resolve a bare href against the current
              // origin, producing a broken /search/[orgnr]/www.dnb.no link —
              // UI audit F03 (2026-04-09).
              const raw = String(org.hjemmeside);
              const href = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
              return (
                <div className="flex justify-between text-sm">
                  <span className="text-[#8A7F74]">Nettsted</span>
                  <a href={href} target="_blank" rel="noopener noreferrer"
                    className="text-[#4A6FA5] flex items-center gap-1 hover:underline">
                    {raw.replace(/^https?:\/\//, "").slice(0, 30)}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              );
            })()}
          </Section>

          {coords?.lat && coords?.lon && (
            <Section title="Lokasjon">
              <CompanyMap lat={coords.lat} lon={coords.lon} label={String(org.navn ?? org.orgnr)} />
            </Section>
          )}
        </div>

        {/* Right: risk + financials + PEP */}
        <div className="space-y-4">
          <Section title="Risikoscore">
            <div className="flex items-center gap-3">
              <RiskBadge score={risk.score as number | undefined} className="text-sm px-3 py-1" />
              <span className="text-2xl font-bold text-[#2C3E50]">
                {risk.score ?? "–"}
                <span className="text-sm font-normal text-[#8A7F74]"> / 20</span>
              </span>
              <span className="text-xs text-[#8A7F74] ml-auto">{riskBand.label}</span>
            </div>
            {/* Gradient bar 0–20 */}
            <div className="space-y-1">
              <div className="relative h-2 rounded-full bg-gradient-to-r from-[#27AE60] via-[#C8A951] to-[#C0392B]">
                {risk.score != null && (
                  <div
                    className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-[#2C3E50] shadow"
                    style={{ left: `calc(${Math.min(100, (risk.score / 20) * 100)}% - 6px)` }}
                  />
                )}
              </div>
              <div className="flex justify-between text-[10px] text-[#C4BDB4] px-0.5">
                <span>0</span><span>5</span><span>10</span><span>15</span><span>20</span>
              </div>
            </div>
            <p className="text-xs text-[#8A7F74] italic">{riskBand.guidance}</p>
          </Section>

          {/* Risk factors breakdown by category — mirrors Streamlit profile_core.py risk table */}
          {factors.length > 0 && (
            <Section title="Risikofaktorer">
              <div className="space-y-3">
                {Object.entries(factorsByCategory).map(([category, items]) => (
                  <div key={category}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ background: CATEGORY_DOTS[category] ?? "#8A7F74" }}
                      />
                      <span className="text-xs font-semibold text-[#2C3E50] uppercase tracking-wide">{category}</span>
                    </div>
                    <ul className="space-y-1 pl-3.5">
                      {items.map((f, i) => (
                        <li key={i} className="flex items-start justify-between gap-2 text-xs">
                          <div className="flex-1">
                            <span className="text-[#2C3E50]">{f.label}</span>
                            {f.detail && <span className="block text-[#C4BDB4] text-[10px]">{f.detail}</span>}
                          </div>
                          <span className="font-mono font-semibold text-[#8A7F74] flex-shrink-0">+{f.points}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-[#C4BDB4] pt-2 border-t border-[#EDE8E3]">
                Skala: 0–3 Lav · 4–7 Moderat · 8–12 Høy · 13+ Svært høy
              </p>
            </Section>
          )}

          {finansData && (
            <Section title={finansData._year ? `Nøkkeltall (${finansData._year})` : "Nøkkeltall"}>
              <KV label="Omsetning"      value={fmtMnok(finansData.sumDriftsinntekter)} />
              <KV label="Nettoresultat"  value={fmtMnok(finansData.arsresultat)} />
              <KV label="Egenkapital"    value={fmtMnok(finansData.sumEgenkapital)} />
              <KV label="Egenkapitalandel"
                value={risk.equity_ratio != null ? `${(Number(risk.equity_ratio) * 100).toFixed(1)}%` : "–"} />
            </Section>
          )}

          {/* PEP */}
          {pep && (Object.keys(pep).length > 0) && (() => {
            const hitCount = (pep.hit_count as number | undefined) ?? 0;
            const query = pep.query as string | undefined;
            const hits = (pep.hits as Record<string, unknown>[] | undefined) ?? [];
            return (
              <Section title="PEP / sanksjonssjekk">
                <div className="flex items-center gap-2 mb-2">
                  {hitCount === 0 ? (
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-700">Ingen treff</span>
                  ) : (
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-red-100 text-red-700 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />{hitCount} treff
                    </span>
                  )}
                  {query && <span className="text-xs text-[#8A7F74]">Søk: {query}</span>}
                </div>
                {hits.map((h, i) => {
                  const datasets = (h.datasets as string[] | undefined) ?? [];
                  const topics   = (h.topics   as string[] | undefined) ?? [];
                  return (
                    <div key={i} className="text-xs border border-[#EDE8E3] rounded-lg p-2 space-y-0.5 mb-1">
                      <p className="font-semibold text-[#2C3E50]">{String(h.name ?? "–")}</p>
                      {!!h.schema    && <p className="text-[#8A7F74]">Type: {String(h.schema)}</p>}
                      {datasets.length > 0 && <p className="text-[#8A7F74]">Datasett: {datasets.join(", ")}</p>}
                      {topics.length   > 0 && <p className="text-[#8A7F74]">Emner: {topics.join(", ")}</p>}
                    </div>
                  );
                })}
              </Section>
            );
          })()}
        </div>
      </div>
      {/* ── End 2-column ─────────────────────────────────────────────── */}

      {/* ── Bottom 2-column grid ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">

        {/* Board members — backend returns {members: [{group, role, name, birth_year, deceased, resigned}]} */}
        {(() => {
          const memberList: BoardMember[] = roles?.members ?? [];
          if (memberList.length === 0) return null;
          const active   = memberList.filter((m) => !m.resigned && !m.deceased);
          const inactive = memberList.filter((m) => m.resigned || m.deceased);
          return (
            <Section title="Styremedlemmer">
              <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
                <Users className="w-3.5 h-3.5" />
                <span>Fra Brønnøysundregistrene</span>
              </div>
              {active.length > 0 && (
                <div className="space-y-1.5">
                  {active.slice(0, 10).map((m, i) => (
                    <div key={i} className="flex justify-between items-baseline text-sm gap-2">
                      <div className="min-w-0">
                        <span className="text-[#2C3E50] font-medium">{m.name || "–"}</span>
                        {m.birth_year && (
                          <span className="text-[#C4BDB4] text-[10px] ml-1.5">f. {m.birth_year}</span>
                        )}
                      </div>
                      <span className="text-[#8A7F74] text-xs text-right flex-shrink-0">{m.role || ""}</span>
                    </div>
                  ))}
                </div>
              )}
              {inactive.length > 0 && (
                <details className="mt-3 pt-2 border-t border-[#EDE8E3]">
                  <summary className="text-xs text-[#8A7F74] cursor-pointer hover:text-[#2C3E50]">
                    Tidligere medlemmer ({inactive.length})
                  </summary>
                  <div className="space-y-1 mt-2">
                    {inactive.slice(0, 10).map((m, i) => (
                      <div key={i} className="flex justify-between items-baseline text-xs gap-2 opacity-70">
                        <div className="min-w-0">
                          <span className="text-[#8A7F74]">{m.name || "–"}</span>
                          {m.birth_year && (
                            <span className="text-[#C4BDB4] text-[10px] ml-1.5">f. {m.birth_year}</span>
                          )}
                        </div>
                        <span className="text-[#C4BDB4] text-[10px] text-right flex-shrink-0">
                          {m.deceased ? "Avdød" : "Fratrådt"} · {m.role || ""}
                        </span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </Section>
          );
        })()}

        {/* Finanstilsynet licenses — backend returns {orgnr, licenses: [{name, license_type, license_status, ...}]} */}
        {(() => {
          const licList = ((licenses as Record<string, unknown> | null)?.licenses as Record<string, unknown>[] | undefined) ?? [];
          if (licList.length === 0) return null;
          return (
            <Section title="Finanstilsynet — konsesjoner">
              <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
                <Shield className="w-3.5 h-3.5" />
                <span>Registrerte finanskonsesjoner</span>
              </div>
              <div className="space-y-1.5">
                {licList.slice(0, 6).map((l, i) => (
                  <div key={i} className="text-xs text-[#2C3E50] flex items-start gap-1.5">
                    <span className="text-[#C8A951] mt-0.5">•</span>
                    <span>
                      {String(l.license_type ?? l.name ?? "Konsesjon")}
                      {!!l.license_status && (
                        <span className="text-[#8A7F74] ml-1">({String(l.license_status)})</span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          );
        })()}

        {/* Industry benchmark — backend returns {orgnr, nace_code, benchmark: {...metrics}}.
            Flattened min/max pairs are collapsed back into ranges here and
            keys are rendered via a Norwegian label map instead of raw
            snake_case. UI audit F08 (2026-04-09). */}
        {benchmark?.benchmark && Object.keys(benchmark.benchmark).length > 0 && (() => {
          const b = benchmark.benchmark as Record<string, unknown>;
          const fmtPct = (v: unknown) => `${(Number(v) * 100).toFixed(0)} %`;
          const fmtRange = (lo: unknown, hi: unknown) => `${fmtPct(lo)} – ${fmtPct(hi)}`;
          const rows: { label: string; value: string }[] = [];
          if (b.industry) rows.push({ label: "Bransje", value: String(b.industry) });
          if (b.section)  rows.push({ label: "Seksjon", value: String(b.section) });
          if (b.typical_equity_ratio_min != null && b.typical_equity_ratio_max != null) {
            rows.push({
              label: "Typisk egenkapitalandel",
              value: fmtRange(b.typical_equity_ratio_min, b.typical_equity_ratio_max),
            });
          }
          if (b.typical_profit_margin_min != null && b.typical_profit_margin_max != null) {
            rows.push({
              label: "Typisk resultatmargin",
              value: fmtRange(b.typical_profit_margin_min, b.typical_profit_margin_max),
            });
          }
          const sourceLive = b.live === true;
          return (
            <Section title="SSB-bransjesammenligning">
              <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
                <TrendingUp className="w-3.5 h-3.5" />
                <span>Typiske nøkkeltall for bransjen{sourceLive ? " (live SSB)" : ""}</span>
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

        {/* Peer benchmark — fetched from /org/{orgnr}/peer-benchmark */}
        {peerData && peerData.peer_count > 0 && (
          <Section title="Bransje-benchmark (peer-sammenligning)">
            <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
              <BarChart3 className="w-3.5 h-3.5" />
              <span>
                NACE-seksjon {peerData.nace_section || "–"} · {peerData.peer_count} {peerData.peer_count === 1 ? "peer" : "peers"} ·{" "}
                {peerData.source === "db_peers" ? "fra database" : "SSB-rangering"}
              </span>
            </div>
            <div className="space-y-2">
              {(["equity_ratio", "revenue", "risk_score"] as const).map((k) => {
                const m = peerData.metrics[k];
                if (m == null || (m.company == null && m.peer_avg == null)) return null;
                const label = k === "equity_ratio" ? "Egenkapitalandel"
                            : k === "revenue"      ? "Omsetning"
                            : "Risikoscore";
                const fmtVal = (v: number | null | undefined) => {
                  if (v == null) return "–";
                  if (k === "equity_ratio") return `${(v * 100).toFixed(1)}%`;
                  if (k === "revenue")      return fmtMnok(v);
                  return v.toFixed(1);
                };
                return (
                  <div key={k} className="flex justify-between items-baseline text-xs">
                    <span className="text-[#8A7F74]">{label}</span>
                    <span className="text-[#2C3E50] font-medium">
                      {fmtVal(m.company)}
                      {" "}<span className="text-[#C4BDB4]">vs</span>{" "}
                      <span className="text-[#8A7F74]">{fmtVal(m.peer_avg)}</span>
                      {m.percentile != null && (
                        <span className="ml-2 text-[10px] text-[#4A6FA5]">P{m.percentile}</span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          </Section>
        )}

        {/* Konsernstruktur — coerce the length check to a boolean so an empty
            sub_units array (length === 0) doesn't leak a stray "0" into the
            DOM. UI audit F11 (2026-04-09). */}
        {struktur && (!!struktur.parent || !!(struktur.sub_units as unknown[] | undefined)?.length) && (
          <Section title="Konsernstruktur">
            {!!struktur.parent && (() => {
              const p = struktur.parent as Record<string, unknown>;
              return (
                <div className="rounded-lg bg-[#F0F4FB] border border-[#C5D0E8] px-3 py-2 mb-3">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-[#4A6FA5] mb-1">Morselskap</p>
                  <p className="text-sm font-semibold text-[#2C3E50]">{String(p.navn ?? "–")}</p>
                  <p className="text-xs text-[#8A7F74]">
                    {[p.orgnr, p.kommune, p.organisasjonsform].filter(Boolean).join(" · ")}
                  </p>
                </div>
              );
            })()}
            {(struktur.sub_units as Record<string, unknown>[] | undefined)?.length ? (
              <div>
                <p className="text-xs font-medium text-[#8A7F74] mb-1.5">
                  Underenheter ({(struktur.total_sub_units as number | undefined) ?? (struktur.sub_units as unknown[]).length})
                </p>
                <div className="space-y-1">
                  {(struktur.sub_units as Record<string, unknown>[]).slice(0, 8).map((s, i) => (
                    <div key={i} className="flex justify-between text-xs">
                      <span className="text-[#2C3E50] font-medium">{String(s.navn ?? "–")}</span>
                      <span className="text-[#8A7F74]">{String(s.orgnr ?? "")}</span>
                    </div>
                  ))}
                  {(struktur.total_sub_units as number | undefined) != null &&
                    (struktur.total_sub_units as number) > 8 && (
                    <p className="text-xs text-[#8A7F74]">
                      + {(struktur.total_sub_units as number) - 8} flere
                    </p>
                  )}
                </div>
              </div>
            ) : null}
          </Section>
        )}

      </div>
      {/* ── End bottom 2-column ──────────────────────────────────────── */}
    </div>
  );
}
