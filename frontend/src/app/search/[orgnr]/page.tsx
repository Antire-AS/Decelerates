"use client";

import { use, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  getOrgProfile, getSlaAgreements, getOrgPolicies, getOrgHistory,
  getOrgRoles, getOrgLicenses, getOrgBankruptcy, getOrgBenchmark,
  getOrgKoordinater,
  addOrgPdfHistory, getOrgExtractionStatus, getOrgFinancialCommentary,
  type OrgProfile, type HistoryRow,
} from "@/lib/api";
import RiskBadge from "@/components/company/RiskBadge";
import WorkflowStepper, { type WorkflowStep } from "@/components/company/WorkflowStepper";
import ContactsSection from "@/components/crm/ContactsSection";
import PoliciesSection from "@/components/crm/PoliciesSection";
import ClaimsSection from "@/components/crm/ClaimsSection";
import ActivitiesSection from "@/components/crm/ActivitiesSection";
import ForsikringSection from "@/components/crm/ForsikringSection";
import NotaterSection from "@/components/company/NotaterSection";
import OrgChatSection from "@/components/company/OrgChatSection";
import OverviewTab from "@/components/company/tabs/OverviewTab";
import FinancialsTab from "@/components/company/tabs/FinancialsTab";
import { ArrowLeft, Loader2 } from "lucide-react";

export default function OrgProfilePage({
  params,
}: {
  params: Promise<{ orgnr: string }>;
}) {
  const { orgnr } = use(params);

  const { data: prof, isLoading } = useSWR<OrgProfile>(
    `org-${orgnr}`,
    () => getOrgProfile(orgnr),
  );
  const { data: slaList } = useSWR<unknown[]>("sla", getSlaAgreements);
  // Policies are fetched here to pass into ClaimsSection (requires policy selector)
  const { data: policies = [] } = useSWR(
    `policies-${orgnr}`,
    () => getOrgPolicies(orgnr),
  );

  const [activeTab, setActiveTab] = useState<"oversikt" | "okonomi" | "forsikring" | "crm" | "notater" | "chat">(
    "oversikt",
  );

  // PDF history form state
  const [pdfUrl, setPdfUrl]     = useState("");
  const [pdfYear, setPdfYear]   = useState(new Date().getFullYear() - 1);
  const [pdfLabel, setPdfLabel] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfErr, setPdfErr]     = useState<string | null>(null);
  const [pdfOk, setPdfOk]       = useState(false);

  // Økonomi tab extras
  const [expandedYear, setExpandedYear] = useState<number | null>(null);
  const [commentary, setCommentary]     = useState<string | null>(null);
  const [commentaryLoading, setCommentaryLoading] = useState(false);
  const [commentaryErr, setCommentaryErr]         = useState<string | null>(null);

  // Load history for both tabs — Oversikt uses the latest row as fallback when BRREG has no data (e.g. banks)
  const { data: historyData, isLoading: historyLoading } = useSWR<HistoryRow[]>(
    `history-${orgnr}`,
    () => getOrgHistory(orgnr),
  );
  const { data: extractionStatus } = useSWR(
    activeTab === "okonomi" ? `extraction-status-${orgnr}` : null,
    () => getOrgExtractionStatus(orgnr),
  );

  // Lazy-load extras for Oversikt tab
  const { data: rolesData }      = useSWR(activeTab === "oversikt" ? `roles-${orgnr}` : null, () => getOrgRoles(orgnr));
  const { data: licensesData }   = useSWR(activeTab === "oversikt" ? `licenses-${orgnr}` : null, () => getOrgLicenses(orgnr));
  const { data: bankruptcyData } = useSWR(activeTab === "oversikt" ? `bankruptcy-${orgnr}` : null, () => getOrgBankruptcy(orgnr));
  const { data: benchmarkData }  = useSWR(activeTab === "oversikt" ? `benchmark-${orgnr}` : null, () => getOrgBenchmark(orgnr));
  const { data: koordinaterData }= useSWR(activeTab === "oversikt" ? `koordinater-${orgnr}` : null, () => getOrgKoordinater(orgnr));

  const roles     = rolesData     as Record<string, unknown> | null | undefined;
  const licenses  = licensesData  as Record<string, unknown> | null | undefined;
  const bankruptcy= bankruptcyData as Record<string, unknown> | null | undefined;
  const benchmark = benchmarkData as Record<string, unknown> | null | undefined;

  const history: HistoryRow[] = historyData ?? [];

  async function handleCommentary() {
    setCommentaryLoading(true); setCommentaryErr(null);
    try {
      const r = await getOrgFinancialCommentary(orgnr);
      setCommentary(r.commentary);
    } catch (e) { setCommentaryErr(String(e)); }
    finally { setCommentaryLoading(false); }
  }

  async function handleAddPdf() {
    if (!pdfUrl.trim() || !pdfYear) return;
    setPdfLoading(true); setPdfErr(null); setPdfOk(false);
    try {
      await addOrgPdfHistory(orgnr, { pdf_url: pdfUrl.trim(), year: pdfYear, label: pdfLabel });
      setPdfUrl(""); setPdfLabel(""); setPdfOk(true);
    } catch (e) { setPdfErr(String(e)); }
    finally { setPdfLoading(false); }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-[#4A6FA5]" />
      </div>
    );
  }

  if (!prof) {
    return (
      <div className="broker-card text-center text-sm text-[#8A7F74]">
        Selskapet ble ikke funnet.{" "}
        <Link href="/search" className="text-[#4A6FA5] underline">Tilbake</Link>
      </div>
    );
  }

  const org  = prof.org  ?? {};
  const regn = prof.regnskap ?? {};
  const risk = prof.risk ?? {};
  const pep  = prof.pep  ?? {};

  const hasContract = Array.isArray(slaList) &&
    slaList.some((s: unknown) => (s as Record<string, unknown>).client_orgnr === orgnr);

  const steps: WorkflowStep[] = [
    { label: "Datainnhenting",   desc: "Selskapsdata fra BRREG",            done: true },
    { label: "Risikovurdering",  desc: "Risikoscore og AI-narrativ",         done: risk.score != null },
    { label: "Behovsanalyse",    desc: "Forsikringsbehov estimert",          done: false },
    { label: "Tilbud innhentet", desc: "Tilbud fra forsikringsselskaper",    done: false },
    { label: "Tilbudsanalyse",   desc: "AI-sammenligning fullført",          done: false },
    { label: "Presentasjon",     desc: "Forsikringstilbud PDF generert",     done: false },
    { label: "Kontrakt",         desc: "Tjenesteavtale signert i Avtaler",   done: hasContract },
  ];

  const TAB_CLS = (t: string) =>
    `px-4 py-2 text-sm font-medium rounded-lg transition-colors cursor-pointer ${
      activeTab === t
        ? "bg-[#2C3E50] text-white"
        : "text-[#8A7F74] hover:bg-[#EDE8E3]"
    }`;

  return (
    <div className="space-y-5">
      {/* Back link */}
      <Link
        href="/search"
        className="inline-flex items-center gap-1 text-sm text-[#8A7F74] hover:text-[#2C3E50]"
      >
        <ArrowLeft className="w-4 h-4" />
        Tilbake til søk
      </Link>

      {/* Company header */}
      <div className="broker-card">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-[#2C3E50]">
              {String(org.navn ?? orgnr)}
            </h1>
            <p className="text-sm text-[#8A7F74] mt-1">
              {orgnr}
              {!!org.organisasjonsform && ` · ${String(org.organisasjonsform)}`}
              {!!org.naeringskode1_beskrivelse && ` · ${String(org.naeringskode1_beskrivelse)}`}
            </p>
          </div>
          <RiskBadge score={risk.score as number | undefined} className="text-sm px-3 py-1" />
        </div>
      </div>

      {/* Workflow stepper */}
      <WorkflowStepper steps={steps} />

      {/* Tab navigation */}
      <div className="flex gap-2 flex-wrap">
        {(["oversikt", "okonomi", "forsikring", "crm", "notater", "chat"] as const).map((t) => (
          <button key={t} onClick={() => setActiveTab(t)} className={TAB_CLS(t)}>
            {t === "oversikt"   ? "Oversikt"   :
             t === "okonomi"    ? "Økonomi"    :
             t === "forsikring" ? "Forsikring" :
             t === "crm"        ? "CRM"        :
             t === "notater"    ? "Notater"    : "Chat"}
          </button>
        ))}
      </div>

      {/* ── Oversikt ─────────────────────────────────────────────────── */}
      {activeTab === "oversikt" && (
        <OverviewTab
          org={org as Record<string, unknown>}
          regn={regn as Record<string, unknown>}
          history={history}
          risk={risk as { score?: number; reasons?: string[]; equity_ratio?: number }}
          pep={pep as Record<string, unknown>}
          koordinaterData={koordinaterData}
          roles={roles}
          licenses={licenses}
          bankruptcy={bankruptcy}
          benchmark={benchmark}
        />
      )}

      {/* ── Økonomi ─────────────────────────────────────────────────── */}
      {activeTab === "okonomi" && (
        <FinancialsTab
          history={history}
          historyLoading={historyLoading}
          extractionStatus={extractionStatus}
          expandedYear={expandedYear}
          setExpandedYear={setExpandedYear}
          commentary={commentary}
          commentaryLoading={commentaryLoading}
          commentaryErr={commentaryErr}
          handleCommentary={handleCommentary}
          pdfUrl={pdfUrl}
          setPdfUrl={setPdfUrl}
          pdfYear={pdfYear}
          setPdfYear={setPdfYear}
          pdfLabel={pdfLabel}
          setPdfLabel={setPdfLabel}
          pdfLoading={pdfLoading}
          pdfErr={pdfErr}
          pdfOk={pdfOk}
          handleAddPdf={handleAddPdf}
          setPdfOk={setPdfOk}
        />
      )}

      {/* ── Forsikring ──────────────────────────────────────────────── */}
      {activeTab === "forsikring" && (
        <ForsikringSection orgnr={orgnr} />
      )}

      {/* ── CRM ─────────────────────────────────────────────────────── */}
      {activeTab === "crm" && (
        <div className="space-y-4">
          <ContactsSection orgnr={orgnr} />
          <PoliciesSection orgnr={orgnr} />
          <ClaimsSection orgnr={orgnr} policies={policies} />
          <ActivitiesSection orgnr={orgnr} />
        </div>
      )}

      {/* ── Notater ──────────────────────────────────────────────────── */}
      {activeTab === "notater" && (
        <NotaterSection orgnr={orgnr} />
      )}

      {/* ── Chat ─────────────────────────────────────────────────────── */}
      {activeTab === "chat" && (
        <OrgChatSection orgnr={orgnr} orgName={String(org.navn ?? orgnr)} />
      )}
    </div>
  );
}
