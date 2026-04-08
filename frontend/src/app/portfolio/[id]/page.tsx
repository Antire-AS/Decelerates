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

const PortfolioMap = dynamic(
  () => import("@/components/portfolio/PortfolioMap"),
  { ssr: false },
);

export default function PortfolioDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
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
        <Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" />
      </div>
    );
  }

  if (!portfolio) {
    return (
      <div className="broker-card text-center py-10 max-w-md mx-auto mt-12">
        <p className="text-sm font-semibold text-[#2C3E50]">Portefølje ikke funnet</p>
        <p className="text-xs text-[#8A7F74] mt-1">ID {portfolioId} eksisterer ikke eller er slettet.</p>
        <Link
          href="/portfolio"
          className="text-xs text-[#4A6FA5] hover:underline mt-3 inline-flex items-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" /> Tilbake til porteføljer
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
            className="text-xs text-[#8A7F74] hover:text-[#4A6FA5] flex items-center gap-1 mb-2"
          >
            <ArrowLeft className="w-3 h-3" /> Alle porteføljer
          </Link>
          <h1 className="text-2xl font-bold text-[#2C3E50]">{portfolio.name}</h1>
          {portfolio.description && (
            <p className="text-sm text-[#8A7F74] mt-0.5">{portfolio.description}</p>
          )}
        </div>
        <button
          onClick={handleDownloadPdf}
          disabled={pdfDownloading}
          className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-[#D4C9B8] text-[#8A7F74] hover:bg-[#EDE8E3] disabled:opacity-50"
        >
          {pdfDownloading
            ? <Loader2 className="w-4 h-4 animate-spin" />
            : <Download className="w-4 h-4" />}
          Last ned PDF-rapport
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
          <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">Konsentrasjon</h2>
          <PortfolioConcentration concentration={concentration} />
        </div>
      )}

      {/* ── Risk table ── */}
      {risk === undefined ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" />
        </div>
      ) : risk.length === 0 ? (
        <div className="broker-card text-center py-10 text-sm text-[#8A7F74]">
          Ingen selskaper i denne porteføljen ennå.{" "}
          Legg til selskaper via selskapsprofilen (CRM-fanen → Portefølje).
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
          <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">Geografisk oversikt</h2>
          <ErrorBoundary>
            <PortfolioMap rows={risk} />
          </ErrorBoundary>
        </div>
      )}

      {/* ── PDF enrichment ── */}
      <div className="broker-card space-y-3">
        <p className="text-xs font-semibold text-[#2C3E50]">Legg til årsrapport-PDF manuelt</p>
        <p className="text-xs text-[#8A7F74]">
          Lim inn en direkte PDF-URL for et selskap i porteføljen for å berike historikken.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <input
            value={pdfOrgnr}
            onChange={(e) => setPdfOrgnr(e.target.value)}
            placeholder="Orgnr (9 siffer)"
            className="px-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50]"
          />
          <input
            value={pdfUrl}
            onChange={(e) => setPdfUrl(e.target.value)}
            placeholder="https://…/årsrapport.pdf"
            className="px-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50]"
          />
          <div className="flex gap-2">
            <input
              type="number"
              value={pdfYear}
              onChange={(e) => setPdfYear(Number(e.target.value))}
              min={2010} max={new Date().getFullYear()}
              className="w-24 px-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50]"
            />
            <button
              onClick={handlePdfEnrich}
              disabled={pdfLoading || !pdfOrgnr.trim() || !pdfUrl.trim()}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-[#4A6FA5] text-white hover:bg-[#3a5e95] disabled:opacity-50"
            >
              {pdfLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              Legg til
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
