"use client";

import { Fragment } from "react";
import { Loader2, Link2, Info, Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { HistoryRow } from "@/lib/api";

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
  history: HistoryRow[];
  historyLoading: boolean;
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
  history,
  historyLoading,
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

      {/* Add annual report PDF */}
      <Section title="Legg til årsrapport-PDF">
        <div className="flex items-center gap-1.5 mb-3 text-xs text-[#8A7F74]">
          <Link2 className="w-3.5 h-3.5" />
          <span>Lim inn URL til PDF-årsrapport — AI henter ut regnskapstall automatisk</span>
        </div>
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
          className="mt-2 w-full text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50] placeholder:text-[#C4BDB4]"
        />
        {pdfErr && <p className="text-xs text-red-600 mt-1">{pdfErr}</p>}
        {pdfOk  && <p className="text-xs text-green-700 mt-1">Regnskapstall hentet og lagret.</p>}
      </Section>

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
          {/* Estimated data warning */}
          {history.some((r) => r.source === "pdf" || r.source === "estimated") && (
            <div className="broker-card border-l-4 border-[#C8A951] flex items-start gap-2">
              <Info className="w-4 h-4 text-[#C8A951] flex-shrink-0 mt-0.5" />
              <p className="text-xs text-[#8A7F74]">
                Noen tall er hentet fra PDF-årsrapporter og kan avvike fra offisielle BRREG-tall.
              </p>
            </div>
          )}

          {/* Revenue + result bar chart */}
          {chartData.length > 0 && (
            <Section title="Omsetning og resultat (MNOK)">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                  <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => `${v} MNOK`} />
                  <Legend />
                  <Bar dataKey="omsetning" name="Omsetning" fill="#4A6FA5" />
                  <Bar dataKey="resultat" name="Nettoresultat" fill="#2C3E50" />
                </BarChart>
              </ResponsiveContainer>
            </Section>
          )}

          {/* Debt breakdown chart */}
          {(() => {
            const debtData = [...history]
              .sort((a, b) => a.year - b.year)
              .filter((r) => r.sumLangsiktigGjeld != null || r.sumKortsiktigGjeld != null)
              .map((r) => ({
                year: r.year,
                langsiktig: r.sumLangsiktigGjeld != null ? +((r.sumLangsiktigGjeld as number) / 1e6).toFixed(1) : null,
                kortsiktig: r.sumKortsiktigGjeld != null ? +((r.sumKortsiktigGjeld as number) / 1e6).toFixed(1) : null,
              }));
            return debtData.length > 0 ? (
              <Section title="Gjeldsstruktur (MNOK)">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={debtData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number) => `${v} MNOK`} />
                    <Legend />
                    <Bar dataKey="langsiktig" name="Langsiktig gjeld" fill="#C8A951" stackId="a" />
                    <Bar dataKey="kortsiktig" name="Kortsiktig gjeld" fill="#E8D5A0" stackId="a" />
                  </BarChart>
                </ResponsiveContainer>
              </Section>
            ) : null;
          })()}

          {/* Equity ratio trend */}
          {eqData.length > 0 && (
            <Section title="Egenkapitalandel (%)">
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={eqData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                  <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} unit="%" />
                  <Tooltip formatter={(v: number) => `${v}%`} />
                  <Line type="monotone" dataKey="ekAndel" name="EK-andel" stroke="#4A6FA5" strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </Section>
          )}

          {/* AI commentary */}
          <div className="broker-card">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
                <Sparkles className="w-4 h-4" /> AI-finanskommentar
              </h3>
              <button
                onClick={handleCommentary}
                disabled={commentaryLoading}
                className="px-3 py-1 text-xs rounded bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1"
              >
                {commentaryLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                Generer kommentar
              </button>
            </div>
            {commentaryErr && <p className="text-xs text-red-600 mt-2">{commentaryErr}</p>}
            {commentary && (
              <div className="mt-3 bg-[#F9F7F4] rounded-lg p-3">
                <p className="text-xs text-[#2C3E50] whitespace-pre-wrap leading-relaxed">{commentary}</p>
              </div>
            )}
          </div>

          {/* YoY History table with drill-down */}
          <Section title="Historikk per år — klikk rad for detaljer">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[#8A7F74] border-b border-[#EDE8E3]">
                    <th className="text-left pb-1.5 font-medium">År</th>
                    <th className="text-right pb-1.5 font-medium">Omsetning</th>
                    <th className="text-right pb-1.5 font-medium">Nettoresultat</th>
                    <th className="text-right pb-1.5 font-medium hidden sm:table-cell">Margin</th>
                    <th className="text-right pb-1.5 font-medium">Egenkapital</th>
                    <th className="text-right pb-1.5 font-medium">EK-andel</th>
                    <th className="text-right pb-1.5 font-medium hidden md:table-cell">Ansatte</th>
                    <th className="w-6 pb-1.5"></th>
                  </tr>
                </thead>
                <tbody>
                  {[...history].sort((a, b) => b.year - a.year).map((r) => {
                    const rev = (r.revenue ?? r.sumDriftsinntekter) as number | undefined;
                    const net = r.arsresultat as number | undefined;
                    const margin = rev && net ? ((net / rev) * 100).toFixed(1) : null;
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
                          <td className="py-1.5 text-right" style={{ color: net != null && net < 0 ? "#C0392B" : "#2C3E50" }}>
                            {fmtMnok(net)}
                          </td>
                          <td className="py-1.5 text-right text-[#8A7F74] hidden sm:table-cell">
                            {margin != null ? `${margin}%` : "–"}
                          </td>
                          <td className="py-1.5 text-right text-[#8A7F74]">{fmtMnok(r.sumEgenkapital)}</td>
                          <td className="py-1.5 text-right text-[#8A7F74]">
                            {r.equity_ratio != null ? `${(r.equity_ratio * 100).toFixed(1)}%` : "–"}
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
                            <td colSpan={8} className="py-3 px-2">
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
                                    ["Resultat før skatt", r.ordinaertResultatForSkattekostnad],
                                    ["Skattekostnad", r.skattekostnadOrdOgEkstraordinaerAktivitet],
                                    ["Årsresultat", r.arsresultat],
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
                                    ["Bankinnskudd", r.bankinnskuddOgKontanter],
                                    ["Omløpsmidler", r.sumOmlopsmidler],
                                    ["Anleggsmidler", r.sumAnleggsmidler],
                                    ["Sum eiendeler", r.sumEiendeler],
                                    ["Egenkapital", r.sumEgenkapital],
                                    ["Langsiktig gjeld", r.sumLangsiktigGjeld],
                                    ["Kortsiktig gjeld", r.sumKortsiktigGjeld],
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
        </>
      )}
    </div>
  );
}
