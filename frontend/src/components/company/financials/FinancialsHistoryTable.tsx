"use client";

import { Fragment } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { HistoryRow } from "@/lib/api";
import { fmt, fmtMnok } from "@/lib/format";
import { useT } from "@/lib/i18n";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="broker-card space-y-3">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </div>
  );
}

function deltaClass(val: string | null): string {
  if (!val) return "text-muted-foreground";
  return val.startsWith("+") ? "text-green-600" : "text-red-600";
}

interface Props {
  history: HistoryRow[];
  expandedYear: number | null;
  setExpandedYear: (year: number | null) => void;
}

export default function FinancialsHistoryTable({ history, expandedYear, setExpandedYear }: Props) {
  const T = useT();
  const sorted = [...history].sort((a, b) => a.year - b.year);

  type YearMeta = {
    row: HistoryRow;
    rev: number | undefined;
    net: number | undefined;
    driftsres: number | undefined;
    margin: number | null;
    driftsmargin: number | null;
    revYoy: string | null;
    marginDelta: string | null;
    ekDelta: string | null;
  };

  const meta: YearMeta[] = sorted.map((r, i) => {
    const rev = (r.revenue ?? r.sumDriftsinntekter) as number | undefined;
    const net = r.arsresultat as number | undefined;
    const driftsres = r.driftsresultat as number | undefined;
    const margin = rev && net ? (net / rev) * 100 : null;
    const driftsmargin = rev && driftsres ? (driftsres / rev) * 100 : null;
    const prev = i > 0 ? sorted[i - 1] : null;
    const prevRev = prev ? ((prev.revenue ?? prev.sumDriftsinntekter) as number | undefined) : null;
    const prevNet = prev ? (prev.arsresultat as number | undefined) : null;
    const prevMargin = prevRev && prevNet ? (prevNet / prevRev) * 100 : null;
    const prevEq = prev?.equity_ratio;

    const revYoy =
      rev != null && prevRev != null && prevRev !== 0
        ? `${((rev - prevRev) / Math.abs(prevRev) * 100) >= 0 ? "+" : ""}${((rev - prevRev) / Math.abs(prevRev) * 100).toFixed(1)}%`
        : null;
    const marginDelta =
      margin != null && prevMargin != null
        ? `${(margin - prevMargin) >= 0 ? "+" : ""}${(margin - prevMargin).toFixed(1)}pp`
        : null;
    const ekDelta =
      r.equity_ratio != null && prevEq != null
        ? `${((r.equity_ratio - prevEq) * 100) >= 0 ? "+" : ""}${((r.equity_ratio - prevEq) * 100).toFixed(1)}pp`
        : null;

    return { row: r, rev, net, driftsres, margin, driftsmargin, revYoy, marginDelta, ekDelta };
  });

  if (sorted.length < 2) return null;

  return (
    <Section title={T("Historikk per år — klikk rad for detaljer")}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground border-b border-border">
              <th className="text-left pb-1.5 font-medium">{T("År")}</th>
              <th className="text-right pb-1.5 font-medium">{T("Omsetning")}</th>
              <th className="text-right pb-1.5 font-medium hidden lg:table-cell">{T("Rev YoY")}</th>
              <th className="text-right pb-1.5 font-medium hidden xl:table-cell">{T("Driftsresultat")}</th>
              <th className="text-right pb-1.5 font-medium hidden xl:table-cell">{T("Dr.margin")}</th>
              <th className="text-right pb-1.5 font-medium">{T("Nettoresultat")}</th>
              <th className="text-right pb-1.5 font-medium hidden sm:table-cell">{T("Margin")}</th>
              <th className="text-right pb-1.5 font-medium hidden lg:table-cell">{T("Margin Δ")}</th>
              <th className="text-right pb-1.5 font-medium">{T("Egenkapital")}</th>
              <th className="text-right pb-1.5 font-medium">{T("EK-andel")}</th>
              <th className="text-right pb-1.5 font-medium hidden lg:table-cell">{T("EK Δ")}</th>
              <th className="text-right pb-1.5 font-medium hidden md:table-cell">{T("Ansatte")}</th>
              <th className="w-6 pb-1.5"></th>
            </tr>
          </thead>
          <tbody>
            {[...meta].reverse().map(({ row: r, rev, net, driftsres, margin, driftsmargin, revYoy, marginDelta, ekDelta }) => {
              const isExp = expandedYear === r.year;
              return (
                <Fragment key={r.year}>
                  <tr
                    className="hover:bg-muted border-b border-border cursor-pointer"
                    onClick={() => setExpandedYear(isExp ? null : r.year)}
                  >
                    <td className="py-1.5 font-medium text-foreground flex items-center gap-1">
                      {r.year}
                      {r.source === "pdf" && (
                        <span className="text-brand-warning text-[10px] font-normal">(PDF)</span>
                      )}
                    </td>
                    <td className="py-1.5 text-right text-muted-foreground">{fmtMnok(rev)}</td>
                    <td className={`py-1.5 text-right hidden lg:table-cell font-medium ${deltaClass(revYoy)}`}>
                      {revYoy ?? "–"}
                    </td>
                    <td className="py-1.5 text-right text-muted-foreground hidden xl:table-cell"
                      style={{ color: driftsres != null && driftsres < 0 ? "#C0392B" : undefined }}>
                      {fmtMnok(driftsres)}
                    </td>
                    <td className="py-1.5 text-right text-muted-foreground hidden xl:table-cell">
                      {driftsmargin != null ? `${driftsmargin.toFixed(1)}%` : "–"}
                    </td>
                    <td className="py-1.5 text-right" style={{ color: net != null && net < 0 ? "#C0392B" : "#2C3E50" }}>
                      {fmtMnok(net)}
                    </td>
                    <td className="py-1.5 text-right text-muted-foreground hidden sm:table-cell">
                      {margin != null ? `${margin.toFixed(1)}%` : "–"}
                    </td>
                    <td className={`py-1.5 text-right hidden lg:table-cell font-medium ${deltaClass(marginDelta)}`}>
                      {marginDelta ?? "–"}
                    </td>
                    <td className="py-1.5 text-right text-muted-foreground">{fmtMnok(r.sumEgenkapital)}</td>
                    <td className="py-1.5 text-right text-muted-foreground">
                      {r.equity_ratio != null ? `${(r.equity_ratio * 100).toFixed(1)}%` : "–"}
                    </td>
                    <td className={`py-1.5 text-right hidden lg:table-cell font-medium ${deltaClass(ekDelta)}`}>
                      {ekDelta ?? "–"}
                    </td>
                    <td className="py-1.5 text-right text-muted-foreground hidden md:table-cell">
                      {fmt(r.antallAnsatte) !== "–" ? fmt(r.antallAnsatte) : "–"}
                    </td>
                    <td className="py-1.5 text-right text-muted-foreground">
                      {isExp ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />}
                    </td>
                  </tr>
                  {isExp && (
                    <tr key={`${r.year}-detail`} className="bg-muted">
                      <td colSpan={13} className="py-3 px-2">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <p className="text-xs font-semibold text-foreground mb-2">{T("Resultatregnskap")}</p>
                            {([
                              [T("Salgsinntekter"), r.salgsinntekter],
                              [T("Sum driftsinntekter"), r.sumDriftsinntekter],
                              [T("Varekostnad"), r.kostnadSolgtVare],
                              [T("Lønnskostnad"), r.lonnskostnad],
                              [T("Avskrivninger"), r.avskrivningDriftslosore],
                              [T("Andre driftskostnader"), r.annenDriftskostnad],
                              [T("Sum driftskostnader"), r.sumDriftskostnader],
                              [T("Driftsresultat"), r.driftsresultat],
                              [T("Finansinntekter"), r.sumFinansinntekter],
                              [T("Finanskostnader"), r.sumFinanskostnader],
                              [T("Netto finans"), r.nettoFinans ?? (
                                r.sumFinansinntekter != null && r.sumFinanskostnader != null
                                  ? (r.sumFinansinntekter as number) - (r.sumFinanskostnader as number)
                                  : null
                              )],
                              [T("Resultat før skatt"), r.ordinaertResultatForSkattekostnad],
                              [T("Skattekostnad"), r.skattekostnadOrdOgEkstraordinaerAktivitet],
                              [T("Årsresultat"), r.arsresultat],
                              [T("Totalresultat"), r.totalresultat],
                            ] as [string, unknown][]).map(([label, val]) => val != null ? (
                              <div key={label} className="flex justify-between text-xs py-0.5 border-b border-border">
                                <span className="text-muted-foreground">{label}</span>
                                <span className={`font-medium ${Number(val) < 0 ? "text-red-600" : "text-foreground"}`}>
                                  {fmtMnok(val)}
                                </span>
                              </div>
                            ) : null)}
                          </div>
                          <div>
                            <p className="text-xs font-semibold text-foreground mb-2">{T("Balanse")}</p>
                            {([
                              [T("Varer"), r.sumVarer],
                              [T("Fordringer"), r.sumFordringer],
                              [T("Investeringer"), r.sumInvesteringer],
                              [T("Bankinnskudd"), r.bankinnskuddOgKontanter],
                              [T("Omløpsmidler"), r.sumOmlopsmidler],
                              [T("Goodwill"), r.goodwill],
                              [T("Anleggsmidler"), r.sumAnleggsmidler],
                              [T("Sum eiendeler"), r.sumEiendeler],
                              [T("Innbetalt egenkapital"), r.sumInnskuttEgenkapital],
                              [T("Opptjent egenkapital"), r.sumOpptjentEgenkapital],
                              [T("Egenkapital"), r.sumEgenkapital],
                              [T("Langsiktig gjeld"), r.sumLangsiktigGjeld],
                              [T("Kortsiktig gjeld"), r.sumKortsiktigGjeld],
                              [T("Sum gjeld"), r.sumGjeld],
                              [T("Sum gjeld + EK"), r.sumGjeldOgEgenkapital],
                            ] as [string, unknown][]).map(([label, val]) => val != null ? (
                              <div key={label} className="flex justify-between text-xs py-0.5 border-b border-border">
                                <span className="text-muted-foreground">{label}</span>
                                <span className="font-medium text-foreground">{fmtMnok(val)}</span>
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
}
