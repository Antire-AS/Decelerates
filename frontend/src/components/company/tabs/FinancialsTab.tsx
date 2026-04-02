"use client";

import { Fragment, useState, useEffect } from "react";
import { Loader2, Link2, Info, Sparkles, ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { HistoryRow } from "@/lib/api";
import { getExchangeRate, deleteOrgHistory } from "@/lib/api";

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

interface ExtractionStatus {
  status: string;
  source_years: number[];
  done_years: number[];
  pending_years: number[];
  missing_target_years: number[];
}

interface FinancialsTabProps {
  orgnr: string;
  history: HistoryRow[];
  historyLoading: boolean;
  onHistoryRefetch?: () => void;
  extractionStatus: ExtractionStatus | undefined;
  expandedYear: number | null;
  setExpandedYear: (year: number | null) => void;
  commentary: string | null;
  commentaryLoading: boolean;
  commentaryErr: string | null;
  handleCommentary: () => void;
  pdfUrl: string;
  setPdfUrl: (v: string) => void;
  pdfYear: number;
  setPdfYear: (v: number) => void;
  pdfLabel: string;
  setPdfLabel: (v: string) => void;
  pdfLoading: boolean;
  pdfErr: string | null;
  pdfOk: boolean;
  handleAddPdf: () => void;
  setPdfOk: (v: boolean) => void;
}

export default function FinancialsTab({
  orgnr,
  history,
  historyLoading,
  onHistoryRefetch,
  extractionStatus,
  expandedYear,
  setExpandedYear,
  commentary,
  commentaryLoading,
  commentaryErr,
  handleCommentary,
  pdfUrl,
  setPdfUrl,
  pdfYear,
  setPdfYear,
  pdfLabel,
  setPdfLabel,
  pdfLoading,
  pdfErr,
  pdfOk,
  handleAddPdf,
  setPdfOk,
}: FinancialsTabProps) {
  // Currency detection
  const foreignCurrencies = [...new Set(
    history.map((r) => (r.currency as string | undefined)).filter((c): c is string => !!c && c !== "NOK")
  )];
  const [fxRates, setFxRates] = useState<Record<string, number>>({});
  useEffect(() => {
    if (!foreignCurrencies.length) return;
    Promise.all(
      foreignCurrencies.map((c) => getExchangeRate(c).then((d) => [c, d.nok_rate] as const).catch(() => null))
    ).then((results) => {
      const rates: Record<string, number> = {};
      for (const r of results) if (r) rates[r[0]] = r[1];
      setFxRates(rates);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history.length]);

  // Re-extract state
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);

  async function handleReset() {
    setResetLoading(true); setResetMsg(null);
    try {
      const r = await deleteOrgHistory(orgnr);
      setResetMsg(`Slettet ${r.deleted_rows} rader. Last inn siden på nytt for å hente data på nytt.`);
      onHistoryRefetch?.();
    } catch (e) {
      setResetMsg(`Feil: ${String(e)}`);
    } finally {
      setResetLoading(false);
    }
  }

  const chartData = [...history]
    .sort((a, b) => a.year - b.year)
    .map((r) => ({
      year: r.year,
      omsetning: r.revenue != null
        ? +(r.revenue / 1e6).toFixed(1)
        : r.sumDriftsinntekter != null
          ? +(r.sumDriftsinntekter / 1e6).toFixed(1)
          : null,
      resultat: r.arsresultat != null ? +(r.arsresultat / 1e6).toFixed(1) : null,
    }))
    .filter((r) => r.omsetning != null || r.resultat != null);

  const eqData = [...history]
    .sort((a, b) => a.year - b.year)
    .filter((r) => r.equity_ratio != null)
    .map((r) => ({
      year: r.year,
      ekAndel: +(r.equity_ratio! * 100).toFixed(1),
    }));

  return (
    <div className="space-y-4">
      {/* Extraction status banner */}
      {extractionStatus && extractionStatus.pending_years.length > 0 && (
        <div className="broker-card border-l-4 border-amber-400 flex items-start gap-2">
          <Info className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-[#2C3E50]">
            <span className="font-medium">PDF-utdrag pågår</span> — venter på år:{" "}
            {extractionStatus.pending_years.join(", ")}. Siden oppdateres automatisk.
          </div>
        </div>
      )}
      {extractionStatus && extractionStatus.missing_target_years.length > 0 &&
        extractionStatus.pending_years.length === 0 && (
        <div className="broker-card border-l-4 border-[#D4C9B8] flex items-start gap-2">
          <Info className="w-4 h-4 text-[#C4BDB4] flex-shrink-0 mt-0.5" />
          <p className="text-xs text-[#8A7F74]">
            Mangler årsrapporter for {extractionStatus.missing_target_years.join(", ")}.
            Lim inn PDF-lenker nedenfor for å hente tall.
          </p>
        </div>
      )}

      {/* Add annual report PDF — collapsed by default, open when years are missing */}
      <details
        className="broker-card group"
        open={!!(extractionStatus?.missing_target_years?.length && !extractionStatus?.pending_years?.length)}
      >
        <summary className="cursor-pointer flex items-center gap-1.5 text-sm font-semibold text-[#2C3E50] select-none list-none">
          <Link2 className="w-4 h-4 text-[#4A6FA5]" />
          Legg til årsrapport-PDF
          <span className="ml-auto text-xs text-[#8A7F74] font-normal group-open:hidden">klikk for å åpne</span>
        </summary>
        <div className="mt-3 space-y-2">
          <p className="text-xs text-[#8A7F74]">Lim inn URL til PDF-årsrapport — AI henter ut regnskapstall automatisk</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto_auto]">
            <input
              type="url"
              value={pdfUrl}
              onChange={(e) => { setPdfUrl(e.target.value); setPdfOk(false); }}
              placeholder="https://example.com/arsrapport-2023.pdf"
              className="text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50] placeholder:text-[#C4BDB4]"
            />
            <input
              type="number"
              value={pdfYear}
              onChange={(e) => setPdfYear(Number(e.target.value))}
              min={2000}
              max={new Date().getFullYear()}
              className="text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 w-24 focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50]"
            />
            <button
              onClick={handleAddPdf}
              disabled={pdfLoading || !pdfUrl.trim()}
              className="px-3 py-1.5 text-xs rounded-lg bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1.5 whitespace-nowrap"
            >
              {pdfLoading && <Loader2 className="w-3 h-3 animate-spin" />}
              {pdfLoading ? "Henter…" : "Hent tall"}
            </button>
          </div>
          <input
            type="text"
            value={pdfLabel}
            onChange={(e) => setPdfLabel(e.target.value)}
            placeholder="Etikett (valgfri, f.eks. «Konsern»)"
            className="w-full text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50] placeholder:text-[#C4BDB4]"
          />
          {pdfErr && <p className="text-xs text-red-600">{pdfErr}</p>}
          {pdfOk  && <p className="text-xs text-green-700">Regnskapstall hentet og lagret.</p>}
        </div>
      </details>

      {historyLoading ? (
        <div className="broker-card flex items-center gap-2 text-xs text-[#8A7F74]">
          <Loader2 className="w-4 h-4 animate-spin" /> Henter historikk…
        </div>
      ) : history.length === 0 ? (
        <Section title="Regnskapshistorikk">
          <p className="text-sm text-[#8A7F74]">
            Ingen historiske regnskapsdata tilgjengelig.
            Lim inn en årsrapport-PDF over for å hente tall.
          </p>
        </Section>
      ) : (
        <>
          {/* Foreign currency banner */}
          {foreignCurrencies.length > 0 && (
            <div className="broker-card border-l-4 border-[#4A6FA5] flex items-start gap-2">
              <Info className="w-4 h-4 text-[#4A6FA5] flex-shrink-0 mt-0.5" />
              <p className="text-xs text-[#2C3E50]">
                <span className="font-medium">Fremmed valuta</span> — tall i{" "}
                {foreignCurrencies.join(", ")}.
                {Object.entries(fxRates).map(([ccy, rate]) => (
                  <span key={ccy}> Dagskurs: 1 {ccy} = {rate.toFixed(4)} NOK.</span>
                ))}
              </p>
            </div>
          )}

          {/* Estimated data warning */}
          {history.some((r) => r.source === "pdf" || r.source === "estimated") && (
            <div className="broker-card border-l-4 border-[#C8A951] flex items-start gap-2">
              <Info className="w-4 h-4 text-[#C8A951] flex-shrink-0 mt-0.5" />
              <p className="text-xs text-[#8A7F74]">
                Noen tall er hentet fra PDF-årsrapporter og kan avvike fra offisielle BRREG-tall.
              </p>
            </div>
          )}

          {/* ── YoY key figures comparison ─────────────────────────── */}
          {(() => {
            const sorted = [...history].sort((a, b) => a.year - b.year);
            type MetricDef = {
              label: string;
              get: (r: HistoryRow) => number | undefined | null;
              fmt: (v: number) => string;
              better: "up" | "down" | null;
            };
            const METRICS: MetricDef[] = [
              {
                label: "Omsetning",
                get: r => (r.revenue ?? r.sumDriftsinntekter) as number | undefined,
                fmt: fmtMnok, better: "up",
              },
              {
                label: "Nettoresultat",
                get: r => r.arsresultat as number | undefined,
                fmt: fmtMnok, better: "up",
              },
              {
                label: "Margin (%)",
                get: r => {
                  const rev = (r.revenue ?? r.sumDriftsinntekter) as number | undefined;
                  const net = r.arsresultat as number | undefined;
                  return rev && net ? +((net / rev) * 100).toFixed(1) : undefined;
                },
                fmt: v => `${v.toFixed(1)}%`, better: "up",
              },
              {
                label: "Sum eiendeler",
                get: r => (r.sumEiendeler ?? r.total_assets) as number | undefined,
                fmt: fmtMnok, better: null,
              },
              {
                label: "Egenkapital",
                get: r => (r.sumEgenkapital ?? r.equity) as number | undefined,
                fmt: fmtMnok, better: "up",
              },
              {
                label: "EK-andel (%)",
                get: r => r.equity_ratio != null ? +(r.equity_ratio * 100).toFixed(1) : undefined,
                fmt: v => `${v.toFixed(1)}%`, better: "up",
              },
              {
                label: "Ansatte",
                get: r => r.antallAnsatte as number | undefined,
                fmt: v => String(Math.round(v)), better: null,
              },
            ];
            const active = METRICS.filter(m => sorted.some(r => m.get(r) != null));
            if (active.length === 0 || sorted.length < 2) return null;
            return (
              <Section title="Nøkkeltall per år">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-[#8A7F74] border-b border-[#EDE8E3]">
                        <th className="text-left pb-2 font-medium w-28">Nøkkeltall</th>
                        {sorted.map(r => (
                          <th key={r.year} className="text-right pb-2 font-medium min-w-[80px]">
                            {r.year}
                            {r.source === "pdf" && (
                              <span className="text-[#C8A951] font-normal ml-1 text-[10px]">PDF</span>
                            )}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {active.map(m => (
                        <tr key={m.label} className="border-b border-[#EDE8E3] last:border-0 hover:bg-[#F9F7F4]">
                          <td className="py-2 text-[#8A7F74] font-medium">{m.label}</td>
                          {sorted.map((r, i) => {
                            const val = m.get(r);
                            const prev = i > 0 ? m.get(sorted[i - 1]) : null;
                            let arrow = "";
                            let arrowCls = "text-[#8A7F74]";
                            if (val != null && prev != null) {
                              if (val > prev) {
                                arrow = "↑";
                                arrowCls = m.better === "up" ? "text-green-600" : m.better === "down" ? "text-red-600" : "text-[#8A7F74]";
                              } else if (val < prev) {
                                arrow = "↓";
                                arrowCls = m.better === "up" ? "text-red-600" : m.better === "down" ? "text-green-600" : "text-[#8A7F74]";
                              }
                            }
                            return (
                              <td key={r.year} className="py-2 text-right">
                                {val != null ? (
                                  <span className={`font-medium ${m.label === "Nettoresultat" && (val as number) < 0 ? "text-red-600" : "text-[#2C3E50]"}`}>
                                    {m.fmt(val as number)}
                                    {arrow && <span className={`ml-1 text-[10px] ${arrowCls}`}>{arrow}</span>}
                                  </span>
                                ) : (
                                  <span className="text-[#C4BDB4]">–</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
            );
          })()}

          {/* Charts — 2-column grid on medium+ screens */}
          {(() => {
            const debtData = [...history]
              .sort((a, b) => a.year - b.year)
              .filter((r) => r.sumLangsiktigGjeld != null || r.sumKortsiktigGjeld != null)
              .map((r) => ({
                year: r.year,
                langsiktig: r.sumLangsiktigGjeld != null ? +((r.sumLangsiktigGjeld as number) / 1e6).toFixed(1) : null,
                kortsiktig: r.sumKortsiktigGjeld != null ? +((r.sumKortsiktigGjeld as number) / 1e6).toFixed(1) : null,
              }));
            const hasDebt = debtData.length > 0;
            const hasEq   = eqData.length > 0;
            const hasRev  = chartData.length > 0;
            if (!hasRev && !hasDebt && !hasEq) return null;
            return (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {hasRev && (
                  <Section title="Omsetning og resultat (MNOK)">
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                        <XAxis dataKey="year" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip formatter={(v: number) => `${v} MNOK`} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Bar dataKey="omsetning" name="Omsetning" fill="#4A6FA5" />
                        <Bar dataKey="resultat" name="Nettoresultat" fill="#2C3E50" />
                      </BarChart>
                    </ResponsiveContainer>
                  </Section>
                )}
                {hasEq && (
                  <Section title="Egenkapitalandel (%)">
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={eqData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                        <XAxis dataKey="year" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} unit="%" />
                        <Tooltip formatter={(v: number) => `${v}%`} />
                        <Line type="monotone" dataKey="ekAndel" name="EK-andel" stroke="#4A6FA5" strokeWidth={2} dot={{ r: 3 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </Section>
                )}
                {hasDebt && (
                  <Section title="Gjeldsstruktur (MNOK)">
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={debtData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                        <XAxis dataKey="year" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip formatter={(v: number) => `${v} MNOK`} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Bar dataKey="langsiktig" name="Langsiktig gjeld" fill="#C8A951" stackId="a" />
                        <Bar dataKey="kortsiktig" name="Kortsiktig gjeld" fill="#E8D5A0" stackId="a" />
                      </BarChart>
                    </ResponsiveContainer>
                  </Section>
                )}
                {/* AI commentary sits in the grid alongside the charts */}
                <div className="broker-card flex flex-col">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4" /> AI-finanskommentar
                    </h3>
                    <button
                      onClick={handleCommentary}
                      disabled={commentaryLoading}
                      className="px-3 py-1 text-xs rounded bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1"
                    >
                      {commentaryLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                      Generer
                    </button>
                  </div>
                  {commentaryErr && <p className="text-xs text-red-600">{commentaryErr}</p>}
                  {commentary ? (
                    <div className="mt-1 bg-[#F9F7F4] rounded-lg p-3 flex-1">
                      <p className="text-xs text-[#2C3E50] whitespace-pre-wrap leading-relaxed">{commentary}</p>
                    </div>
                  ) : (
                    <p className="text-xs text-[#C4BDB4] mt-2">Klikk «Generer» for AI-analyse av finansiell trendutvikling.</p>
                  )}
                </div>
              </div>
            );
          })()}

          {/* YoY History table with drill-down */}
          {(() => {
            const sorted = [...history].sort((a, b) => a.year - b.year);
            // Precompute per-year deltas (oldest→newest order, then we reverse for display)
            type YearMeta = {
              row: typeof sorted[number];
              rev: number | undefined;
              net: number | undefined;
              margin: number | null;
              revYoy: string | null;
              marginDelta: string | null;
              ekDelta: string | null;
            };
            const meta: YearMeta[] = sorted.map((r, i) => {
              const rev = (r.revenue ?? r.sumDriftsinntekter) as number | undefined;
              const net = r.arsresultat as number | undefined;
              const margin = rev && net ? (net / rev) * 100 : null;
              const prev = i > 0 ? sorted[i - 1] : null;
              const prevRev = prev ? ((prev.revenue ?? prev.sumDriftsinntekter) as number | undefined) : null;
              const prevNet = prev ? (prev.arsresultat as number | undefined) : null;
              const prevMargin = prevRev && prevNet ? (prevNet / prevRev) * 100 : null;
              const prevEq = prev?.equity_ratio;

              const revYoy = rev != null && prevRev != null && prevRev !== 0
                ? `${((rev - prevRev) / Math.abs(prevRev) * 100) >= 0 ? "+" : ""}${((rev - prevRev) / Math.abs(prevRev) * 100).toFixed(1)}%`
                : null;
              const marginDelta = margin != null && prevMargin != null
                ? `${(margin - prevMargin) >= 0 ? "+" : ""}${(margin - prevMargin).toFixed(1)}pp`
                : null;
              const ekDelta = r.equity_ratio != null && prevEq != null
                ? `${((r.equity_ratio - prevEq) * 100) >= 0 ? "+" : ""}${((r.equity_ratio - prevEq) * 100).toFixed(1)}pp`
                : null;

              return { row: r, rev, net, margin, revYoy, marginDelta, ekDelta };
            });

            function deltaClass(val: string | null): string {
              if (!val) return "text-[#8A7F74]";
              return val.startsWith("+") ? "text-green-600" : "text-red-600";
            }

            return (
          <Section title="Historikk per år — klikk rad for detaljer">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[#8A7F74] border-b border-[#EDE8E3]">
                    <th className="text-left pb-1.5 font-medium">År</th>
                    <th className="text-right pb-1.5 font-medium">Omsetning</th>
                    <th className="text-right pb-1.5 font-medium hidden lg:table-cell">Rev YoY</th>
                    <th className="text-right pb-1.5 font-medium">Nettoresultat</th>
                    <th className="text-right pb-1.5 font-medium hidden sm:table-cell">Margin</th>
                    <th className="text-right pb-1.5 font-medium hidden lg:table-cell">Margin Δ</th>
                    <th className="text-right pb-1.5 font-medium">Egenkapital</th>
                    <th className="text-right pb-1.5 font-medium">EK-andel</th>
                    <th className="text-right pb-1.5 font-medium hidden lg:table-cell">EK Δ</th>
                    <th className="text-right pb-1.5 font-medium hidden md:table-cell">Ansatte</th>
                    <th className="w-6 pb-1.5"></th>
                  </tr>
                </thead>
                <tbody>
                  {[...meta].reverse().map(({ row: r, rev, net, margin, revYoy, marginDelta, ekDelta }) => {
                    const isExp = expandedYear === r.year;
                    return (
                      <Fragment key={r.year}>
                        <tr
                          className="hover:bg-[#F9F7F4] border-b border-[#EDE8E3] cursor-pointer"
                          onClick={() => setExpandedYear(isExp ? null : r.year)}
                        >
                          <td className="py-1.5 font-medium text-[#2C3E50] flex items-center gap-1">
                            {r.year}
                            {r.source === "pdf" && (
                              <span className="text-[#C8A951] text-[10px] font-normal">(PDF)</span>
                            )}
                          </td>
                          <td className="py-1.5 text-right text-[#8A7F74]">{fmtMnok(rev)}</td>
                          <td className={`py-1.5 text-right hidden lg:table-cell font-medium ${deltaClass(revYoy)}`}>
                            {revYoy ?? "–"}
                          </td>
                          <td className="py-1.5 text-right" style={{ color: net != null && net < 0 ? "#C0392B" : "#2C3E50" }}>
                            {fmtMnok(net)}
                          </td>
                          <td className="py-1.5 text-right text-[#8A7F74] hidden sm:table-cell">
                            {margin != null ? `${margin.toFixed(1)}%` : "–"}
                          </td>
                          <td className={`py-1.5 text-right hidden lg:table-cell font-medium ${deltaClass(marginDelta)}`}>
                            {marginDelta ?? "–"}
                          </td>
                          <td className="py-1.5 text-right text-[#8A7F74]">{fmtMnok(r.sumEgenkapital)}</td>
                          <td className="py-1.5 text-right text-[#8A7F74]">
                            {r.equity_ratio != null ? `${(r.equity_ratio * 100).toFixed(1)}%` : "–"}
                          </td>
                          <td className={`py-1.5 text-right hidden lg:table-cell font-medium ${deltaClass(ekDelta)}`}>
                            {ekDelta ?? "–"}
                          </td>
                          <td className="py-1.5 text-right text-[#8A7F74] hidden md:table-cell">
                            {fmt(r.antallAnsatte) !== "–" ? fmt(r.antallAnsatte) : "–"}
                          </td>
                          <td className="py-1.5 text-right text-[#C4BDB4]">
                            {isExp ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />}
                          </td>
                        </tr>
                        {isExp && (
                          <tr key={`${r.year}-detail`} className="bg-[#F9F7F4]">
                            <td colSpan={11} className="py-3 px-2">
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                {/* P&L */}
                                <div>
                                  <p className="text-xs font-semibold text-[#2C3E50] mb-2">Resultatregnskap</p>
                                  {[
                                    ["Salgsinntekter", r.salgsinntekter],
                                    ["Sum driftsinntekter", r.sumDriftsinntekter],
                                    ["Varekostnad", r.kostnadSolgtVare],
                                    ["Lønnskostnad", r.lonnskostnad],
                                    ["Avskrivninger", r.avskrivningDriftslosore],
                                    ["Andre driftskostnader", r.annenDriftskostnad],
                                    ["Sum driftskostnader", r.sumDriftskostnader],
                                    ["Driftsresultat", r.driftsresultat],
                                    ["Finansinntekter", r.sumFinansinntekter],
                                    ["Finanskostnader", r.sumFinanskostnader],
                                    ["Netto finans", r.nettoFinans ?? (
                                      r.sumFinansinntekter != null && r.sumFinanskostnader != null
                                        ? (r.sumFinansinntekter as number) - (r.sumFinanskostnader as number)
                                        : null
                                    )],
                                    ["Resultat før skatt", r.ordinaertResultatForSkattekostnad],
                                    ["Skattekostnad", r.skattekostnadOrdOgEkstraordinaerAktivitet],
                                    ["Årsresultat", r.arsresultat],
                                    ["Totalresultat", r.totalresultat],
                                  ].map(([label, val]) => val != null ? (
                                    <div key={String(label)} className="flex justify-between text-xs py-0.5 border-b border-[#EDE8E3]">
                                      <span className="text-[#8A7F74]">{String(label)}</span>
                                      <span className={`font-medium ${Number(val) < 0 ? "text-red-600" : "text-[#2C3E50]"}`}>
                                        {fmtMnok(val)}
                                      </span>
                                    </div>
                                  ) : null)}
                                </div>
                                {/* Balance sheet */}
                                <div>
                                  <p className="text-xs font-semibold text-[#2C3E50] mb-2">Balanse</p>
                                  {[
                                    ["Varer", r.sumVarer],
                                    ["Fordringer", r.sumFordringer],
                                    ["Investeringer", r.sumInvesteringer],
                                    ["Bankinnskudd", r.bankinnskuddOgKontanter],
                                    ["Omløpsmidler", r.sumOmlopsmidler],
                                    ["Goodwill", r.goodwill],
                                    ["Anleggsmidler", r.sumAnleggsmidler],
                                    ["Sum eiendeler", r.sumEiendeler],
                                    ["Innbetalt egenkapital", r.sumInnskuttEgenkapital],
                                    ["Opptjent egenkapital", r.sumOpptjentEgenkapital],
                                    ["Egenkapital", r.sumEgenkapital],
                                    ["Langsiktig gjeld", r.sumLangsiktigGjeld],
                                    ["Kortsiktig gjeld", r.sumKortsiktigGjeld],
                                    ["Sum gjeld", r.sumGjeld],
                                    ["Sum gjeld + EK", r.sumGjeldOgEgenkapital],
                                  ].map(([label, val]) => val != null ? (
                                    <div key={String(label)} className="flex justify-between text-xs py-0.5 border-b border-[#EDE8E3]">
                                      <span className="text-[#8A7F74]">{String(label)}</span>
                                      <span className="font-medium text-[#2C3E50]">{fmtMnok(val)}</span>
                                    </div>
                                  ) : null)}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Section>
            );
          })()}

          {/* Re-extract PDF history */}
          <details className="broker-card group">
            <summary className="cursor-pointer text-xs text-[#8A7F74] flex items-center gap-1.5 select-none">
              <RotateCcw className="w-3.5 h-3.5" />
              Tilbakestill og hent historikk på nytt
            </summary>
            <div className="mt-3 space-y-2">
              <p className="text-xs text-[#8A7F74]">
                Sletter alle lagrede regnskapsrader for dette selskapet og utløser ny henting fra PDF-kildene.
              </p>
              <button
                onClick={handleReset}
                disabled={resetLoading}
                className="px-3 py-1.5 text-xs rounded-lg bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 disabled:opacity-50 flex items-center gap-1.5"
              >
                {resetLoading && <Loader2 className="w-3 h-3 animate-spin" />}
                {resetLoading ? "Sletter…" : "Tilbakestill historikk"}
              </button>
              {resetMsg && <p className="text-xs text-[#2C3E50]">{resetMsg}</p>}
            </div>
          </details>
        </>
      )}
    </div>
  );
}

