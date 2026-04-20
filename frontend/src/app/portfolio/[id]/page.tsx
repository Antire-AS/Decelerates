"use client";

import { use, useState } from "react";
import dynamic from "next/dynamic";
import useSWR from "swr";
import Link from "next/link";
import { ArrowLeft, Download, Loader2 } from "lucide-react";
import {
  getPortfolio,
  getPortfolioRisk,
  getPortfolioAlerts,
  getPortfolioConcentration,
  removePortfolioCompany,
  downloadPortfolioPdf,
  portfolioChat,
  addOrgPdfHistory,
  type PortfolioItem,
  type PortfolioRiskRow,
} from "@/lib/api";
import { PortfolioRiskTable } from "@/components/portfolio/PortfolioRiskTable";
import { PortfolioAlerts } from "@/components/portfolio/PortfolioAlerts";
import { PortfolioConcentration } from "@/components/portfolio/PortfolioConcentration";
import { PortfolioChat } from "@/components/portfolio/PortfolioChat";
import { PortfolioIngest } from "@/components/portfolio/PortfolioIngest";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useT } from "@/lib/i18n";

const PortfolioMap = dynamic(
  () => import("@/components/portfolio/PortfolioMap"),
  { ssr: false },
);

export default function PortfolioDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const T = useT();
  const { id } = use(params);
  const portfolioId = Number(id);

  const { data: portfolio } = useSWR<PortfolioItem>(
    `portfolio-${portfolioId}`,
    () => getPortfolio(portfolioId),
  );

  const { data: risk, mutate: mutateRisk } = useSWR<PortfolioRiskRow[]>(
    `portfolio-risk-${portfolioId}`,
    () => getPortfolioRisk(portfolioId),
  );
  const { data: alerts } = useSWR(
    `portfolio-alerts-${portfolioId}`,
    () => getPortfolioAlerts(portfolioId),
  );
  const { data: concentration } = useSWR(
    `portfolio-concentration-${portfolioId}`,
    () => getPortfolioConcentration(portfolioId),
  );

  const [removingOrgnr, setRemovingOrgnr] = useState<string | null>(null);
  const [pdfDownloading, setPdfDownloading] = useState(false);

  // PDF enrichment form
  const [pdfOrgnr, setPdfOrgnr]   = useState("");
  const [pdfUrl, setPdfUrl]       = useState("");
  const [pdfYear, setPdfYear]     = useState(new Date().getFullYear() - 1);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfMsg, setPdfMsg]       = useState<{ ok: boolean; text: string } | null>(null);

  const [chatQuestion, setChatQuestion] = useState("");
  const [chatAnswer, setChatAnswer] = useState<string | null>(null);
  const [chatSources, setChatSources] = useState<string[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatErr, setChatErr] = useState<string | null>(null);

  async function handleRemove(orgnr: string) {
    setRemovingOrgnr(orgnr);
    try {
      await removePortfolioCompany(portfolioId, orgnr);
      mutateRisk();
    } finally {
      setRemovingOrgnr(null);
    }
  }

  async function handleDownloadPdf() {
    setPdfDownloading(true);
    try {
      await downloadPortfolioPdf(portfolioId, portfolio?.name ?? "rapport");
    } finally {
      setPdfDownloading(false);
    }
  }

  async function handlePdfEnrich() {
    if (!pdfOrgnr.trim() || !pdfUrl.trim()) return;
    setPdfLoading(true); setPdfMsg(null);
    try {
      await addOrgPdfHistory(pdfOrgnr.trim(), { pdf_url: pdfUrl.trim(), year: pdfYear });
      setPdfMsg({ ok: true, text: `PDF for ${pdfOrgnr} (${pdfYear}) er lagt til og utdrag starter.` });
      setPdfUrl(""); setPdfOrgnr("");
    } catch (e) {
      setPdfMsg({ ok: false, text: String(e) });
    } finally {
      setPdfLoading(false);
    }
  }

  async function handleChat() {
    if (!chatQuestion.trim()) return;
    setChatLoading(true);
    setChatErr(null);
    setChatAnswer(null);
    try {
      const r = await portfolioChat(portfolioId, chatQuestion);
      setChatAnswer(r.answer);
      setChatSources(r.sources ?? []);
    } catch (e) {
      setChatErr(String(e));
    } finally {
      setChatLoading(false);
    }
  }

  if (!portfolio && portfolio !== null) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  if (!portfolio) {
    return (
      <div className="broker-card text-center py-10 max-w-md mx-auto mt-12">
        <p className="text-sm font-semibold text-foreground">{T("Portefølje ikke funnet")}</p>
        <p className="text-xs text-muted-foreground mt-1">{T("ID {id} eksisterer ikke eller er slettet.").replace("{id}", String(portfolioId))}</p>
        <Link
          href="/portfolio"
          className="text-xs text-primary hover:underline mt-3 inline-flex items-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" /> {T("Tilbake til porteføljer")}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <Link
            href="/portfolio"
            className="text-xs text-muted-foreground hover:text-primary flex items-center gap-1 mb-2"
          >
            <ArrowLeft className="w-3 h-3" /> {T("Alle porteføljer")}
          </Link>
          <h1 className="text-2xl font-bold text-foreground">{portfolio.name}</h1>
          {portfolio.description && (
            <p className="text-sm text-muted-foreground mt-0.5">{portfolio.description}</p>
          )}
        </div>
        <button
          onClick={handleDownloadPdf}
          disabled={pdfDownloading}
          className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-border text-muted-foreground hover:bg-muted disabled:opacity-50"
        >
          {pdfDownloading
            ? <Loader2 className="w-4 h-4 animate-spin" />
            : <Download className="w-4 h-4" />}
          {T("Last ned PDF-rapport")}
        </button>
      </div>

      {/* ── Alerts ── */}
      {alerts && alerts.length > 0 && (
        <div className="broker-card">
          <PortfolioAlerts alerts={alerts} />
        </div>
      )}

      {/* ── Concentration ── */}
      {concentration && (
        <div className="broker-card">
          <h2 className="text-sm font-semibold text-foreground mb-3">{T("Konsentrasjon")}</h2>
          <PortfolioConcentration concentration={concentration} />
        </div>
      )}

      {/* ── Risk table ── */}
      {risk === undefined ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      ) : risk.length === 0 ? (
        <div className="broker-card text-center py-10 text-sm text-muted-foreground">
          {T("Ingen selskaper i denne porteføljen ennå. Legg til selskaper via selskapsprofilen (CRM-fanen → Portefølje).")}
        </div>
      ) : (
        <div className="broker-card">
          <PortfolioRiskTable
            portfolioRisk={risk}
            portfolioName={portfolio.name}
            removingOrgnr={removingOrgnr}
            onRemove={handleRemove}
          />
        </div>
      )}

      {/* ── Geographic map ── */}
      {risk && risk.length > 0 && (
        <div className="broker-card">
          <h2 className="text-sm font-semibold text-foreground mb-3">{T("Geografisk oversikt")}</h2>
          <ErrorBoundary>
            <PortfolioMap rows={risk} />
          </ErrorBoundary>
        </div>
      )}

      {/* ── PDF enrichment ── */}
      <div className="broker-card space-y-3">
        <p className="text-xs font-semibold text-foreground">{T("Legg til årsrapport-PDF manuelt")}</p>
        <p className="text-xs text-muted-foreground">
          {T("Lim inn en direkte PDF-URL for et selskap i porteføljen for å berike historikken.")}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <input
            value={pdfOrgnr}
            onChange={(e) => setPdfOrgnr(e.target.value)}
            placeholder={T("Orgnr (9 siffer)")}
            className="px-3 py-1.5 text-sm border border-border rounded-lg focus:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
          />
          <input
            value={pdfUrl}
            onChange={(e) => setPdfUrl(e.target.value)}
            placeholder="https://…/årsrapport.pdf"
            className="px-3 py-1.5 text-sm border border-border rounded-lg focus:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
          />
          <div className="flex gap-2">
            <input
              type="number"
              value={pdfYear}
              onChange={(e) => setPdfYear(Number(e.target.value))}
              min={2010} max={new Date().getFullYear()}
              className="w-24 px-3 py-1.5 text-sm border border-border rounded-lg focus:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
            />
            <button
              onClick={handlePdfEnrich}
              disabled={pdfLoading || !pdfOrgnr.trim() || !pdfUrl.trim()}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {pdfLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              {T("Legg til")}
            </button>
          </div>
        </div>
        {pdfMsg && (
          <p className={`text-xs ${pdfMsg.ok ? "text-green-600" : "text-red-600"}`}>{pdfMsg.text}</p>
        )}
      </div>

      {/* ── Ingest + chat ── */}
      <div className="broker-card space-y-0">
        <PortfolioIngest
          portfolioId={portfolioId}
          onDone={() => { mutateRisk(); }}
        />
        <PortfolioChat
          chatQuestion={chatQuestion}
          setChatQuestion={setChatQuestion}
          chatAnswer={chatAnswer}
          chatSources={chatSources}
          chatLoading={chatLoading}
          chatErr={chatErr}
          onSubmit={handleChat}
        />
      </div>

    </div>
  );
}
