"use client";

import { useState, useEffect } from "react";
import { Loader2, RotateCcw } from "lucide-react";
import type { HistoryRow } from "@/lib/api";
import { getExchangeRate, deleteOrgHistory } from "@/lib/api";
import FinancialsBanners from "@/components/company/financials/FinancialsBanners";
import FinancialsKeyFigures from "@/components/company/financials/FinancialsKeyFigures";
import AddPdfForm from "@/components/company/financials/AddPdfForm";
import FinancialsKeyFiguresTable from "@/components/company/financials/FinancialsKeyFiguresTable";
import FinancialsCharts from "@/components/company/financials/FinancialsCharts";
import FinancialsHistoryTable from "@/components/company/financials/FinancialsHistoryTable";

interface ExtractionStatus {
  status: string;
  source_years: number[];
  done_years: number[];
  pending_years: number[];
  missing_target_years: number[];
}

interface FinancialsTabProps {
  orgnr: string;
  regn: Record<string, unknown>;
  equityRatio?: number;
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
  orgnr, regn, equityRatio, history, historyLoading, onHistoryRefetch, extractionStatus,
  expandedYear, setExpandedYear,
  commentary, commentaryLoading, commentaryErr, handleCommentary,
  pdfUrl, setPdfUrl, pdfYear, setPdfYear, pdfLabel, setPdfLabel,
  pdfLoading, pdfErr, pdfOk, handleAddPdf, setPdfOk,
}: FinancialsTabProps) {
  const foreignCurrencies = [...new Set(
    history.map((r) => (r.currency as string | undefined)).filter((c): c is string => !!c && c !== "NOK"),
  )];
  const [fxRates, setFxRates] = useState<Record<string, number>>({});
  useEffect(() => {
    if (!foreignCurrencies.length) return;
    Promise.all(
      foreignCurrencies.map((c) => getExchangeRate(c).then((d) => [c, d.nok_rate] as const).catch(() => null)),
    ).then((results) => {
      const rates: Record<string, number> = {};
      for (const r of results) if (r) rates[r[0]] = r[1];
      setFxRates(rates);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history.length]);

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

  const sorted = [...history].sort((a, b) => a.year - b.year);
  const chartData = sorted
    .map((r) => ({
      year: r.year,
      omsetning: r.revenue != null ? +(r.revenue / 1e6).toFixed(1)
        : r.sumDriftsinntekter != null ? +(r.sumDriftsinntekter / 1e6).toFixed(1) : null,
      resultat: r.arsresultat != null ? +(r.arsresultat / 1e6).toFixed(1) : null,
    }))
    .filter((r) => r.omsetning != null || r.resultat != null);

  const eqData = sorted
    .filter((r) => r.equity_ratio != null)
    .map((r) => ({ year: r.year, ekAndel: +(r.equity_ratio! * 100).toFixed(1) }));

  const debtData = sorted
    .filter((r) => r.sumLangsiktigGjeld != null || r.sumKortsiktigGjeld != null)
    .map((r) => ({
      year: r.year,
      langsiktig: r.sumLangsiktigGjeld != null ? +((r.sumLangsiktigGjeld as number) / 1e6).toFixed(1) : null,
      kortsiktig: r.sumKortsiktigGjeld != null ? +((r.sumKortsiktigGjeld as number) / 1e6).toFixed(1) : null,
    }));

  return (
    <div className="space-y-4">
      <FinancialsBanners
        extractionStatus={extractionStatus}
        foreignCurrencies={foreignCurrencies}
        fxRates={fxRates}
        hasEstimated={history.some((r) => r.source === "pdf" || r.source === "estimated")}
        hasHistory={history.length > 0}
      />
      <FinancialsKeyFigures
        orgnr={orgnr}
        regn={regn}
        equityRatio={equityRatio}
        hasHistory={history.length > 0}
        onEstimated={onHistoryRefetch}
      />
      <AddPdfForm
        pdfUrl={pdfUrl} setPdfUrl={setPdfUrl}
        pdfYear={pdfYear} setPdfYear={setPdfYear}
        pdfLabel={pdfLabel} setPdfLabel={setPdfLabel}
        pdfLoading={pdfLoading} pdfErr={pdfErr} pdfOk={pdfOk}
        handleAddPdf={handleAddPdf} setPdfOk={setPdfOk}
        missingYearsCount={extractionStatus?.missing_target_years?.length ?? 0}
        pendingYearsCount={extractionStatus?.pending_years?.length ?? 0}
      />

      {historyLoading ? (
        <div className="broker-card flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> Henter historikk…
        </div>
      ) : history.length === 0 ? (
        <div className="broker-card space-y-3">
          <h3 className="text-sm font-semibold text-foreground">Regnskapshistorikk</h3>
          <p className="text-sm text-muted-foreground">
            Ingen historiske regnskapsdata tilgjengelig.
            Lim inn en årsrapport-PDF over for å hente tall.
          </p>
        </div>
      ) : (
        <>
          <FinancialsKeyFiguresTable history={history} />
          <FinancialsCharts
            chartData={chartData} eqData={eqData} debtData={debtData}
            commentary={commentary} commentaryLoading={commentaryLoading}
            commentaryErr={commentaryErr} handleCommentary={handleCommentary}
          />
          <FinancialsHistoryTable
            history={history}
            expandedYear={expandedYear}
            setExpandedYear={setExpandedYear}
          />
          <details className="broker-card group">
            <summary className="cursor-pointer text-xs text-muted-foreground flex items-center gap-1.5 select-none">
              <RotateCcw className="w-3.5 h-3.5" />
              Tilbakestill og hent historikk på nytt
            </summary>
            <div className="mt-3 space-y-2">
              <p className="text-xs text-muted-foreground">
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
              {resetMsg && <p className="text-xs text-foreground">{resetMsg}</p>}
            </div>
          </details>
        </>
      )}
    </div>
  );
}
