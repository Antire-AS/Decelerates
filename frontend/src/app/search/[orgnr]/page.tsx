"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  getOrgProfile, getSlaAgreements, getOrgPolicies, getOrgHistory,
  getOrgRoles, getOrgLicenses, getOrgBankruptcy, getOrgBenchmark,
  getOrgKoordinater, getOrgStruktur,
  addOrgPdfHistory, getOrgExtractionStatus, getOrgFinancialCommentary,
  getOrgSubmissions, downloadCertificatePdf, getOrgRecommendations,
  type OrgProfile, type HistoryRow,
} from "@/lib/api";
import RiskBadge from "@/components/company/RiskBadge";
import { useRiskConfig, bandTailwindClass } from "@/lib/useRiskConfig";
import AnbudPackageButton from "@/components/company/AnbudPackageButton";
import WorkflowStepper, { type WorkflowStep } from "@/components/company/WorkflowStepper";
import dynamic from "next/dynamic";
import { useT } from "@/lib/i18n";

const ContactsSection    = dynamic(() => import("@/components/crm/ContactsSection"));
const PoliciesSection    = dynamic(() => import("@/components/crm/PoliciesSection"));
const ClaimsSection      = dynamic(() => import("@/components/crm/ClaimsSection"));
const ActivitiesSection  = dynamic(() => import("@/components/crm/ActivitiesSection"));
const ForsikringSection  = dynamic(() => import("@/components/crm/ForsikringSection"));
const ClientPortalSection = dynamic(() => import("@/components/crm/ClientPortalSection"));
const SubmissionsSection = dynamic(() => import("@/components/crm/SubmissionsSection"));
const RecommendationsSection = dynamic(() => import("@/components/crm/RecommendationsSection"));
const CoverageSection = dynamic(() => import("@/components/company/CoverageSection"));
const PropertySection = dynamic(() =>
  import("@/components/company/PropertySection").then((m) => m.PropertySection),
);
import PremiumBenchmark from "@/components/company/PremiumBenchmark";
import NotaterSection from "@/components/company/NotaterSection";
import OrgChatSection from "@/components/company/OrgChatSection";
import WhiteboardTab from "@/components/company/WhiteboardTab";
import NewsTab from "@/components/company/tabs/NewsTab";
import OverviewTab from "@/components/company/tabs/OverviewTab";
import FinancialsTab from "@/components/company/tabs/FinancialsTab";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Loader2, FileText, Download, AlertTriangle } from "lucide-react";

export default function OrgProfilePage({
  params,
}: {
  params: Promise<{ orgnr: string }>;
}) {
  const { orgnr } = use(params);
  const T = useT();
  const { bandFor } = useRiskConfig();

  const [activeTab, setActiveTab] = useState<"oversikt" | "okonomi" | "forsikring" | "crm" | "notater" | "chat" | "fokus" | "nyheter">(
    "oversikt",
  );

  const { data: prof, isLoading } = useSWR<OrgProfile>(
    `org-${orgnr}`,
    () => getOrgProfile(orgnr),
  );
  const { data: slaList } = useSWR<unknown[]>("sla", getSlaAgreements);
  // Policies only needed in CRM tab — defer until tab is active
  const { data: policies, isLoading: policiesLoading } = useSWR(
    activeTab === "crm" ? `policies-${orgnr}` : null,
    () => getOrgPolicies(orgnr),
  );
  const { data: submissions = [] } = useSWR(
    `submissions-${orgnr}`,
    () => getOrgSubmissions(orgnr),
  );
  const { data: recommendations = [] } = useSWR(
    `recommendations-${orgnr}`,
    () => getOrgRecommendations(orgnr),
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
  const { data: historyData, isLoading: historyLoading, mutate: mutateHistory } = useSWR<HistoryRow[]>(
    `history-${orgnr}`,
    () => getOrgHistory(orgnr),
  );
  const { data: extractionStatus } = useSWR(
    activeTab === "okonomi" ? `extraction-status-${orgnr}` : null,
    () => getOrgExtractionStatus(orgnr),
  );

  // Lazy-load extras for Oversikt tab — types are inferred from generated openapi schema
  const { data: roles }       = useSWR(activeTab === "oversikt" ? `roles-${orgnr}` : null, () => getOrgRoles(orgnr));
  const { data: licenses }    = useSWR(activeTab === "oversikt" ? `licenses-${orgnr}` : null, () => getOrgLicenses(orgnr));
  const { data: bankruptcy }  = useSWR(activeTab === "oversikt" ? `bankruptcy-${orgnr}` : null, () => getOrgBankruptcy(orgnr));
  const { data: benchmark }   = useSWR(activeTab === "oversikt" ? `benchmark-${orgnr}` : null, () => getOrgBenchmark(orgnr));
  const { data: koordinaterData } = useSWR(activeTab === "oversikt" ? `koordinater-${orgnr}` : null, () => getOrgKoordinater(orgnr));
  const { data: strukturData }    = useSWR(activeTab === "oversikt" ? `struktur-${orgnr}`    : null, () => getOrgStruktur(orgnr));

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

  // Track recently viewed companies for the search page "Nylig sett" section.
  // Must be before early returns to satisfy React hooks rules-of-hooks.
  const profNavn = prof?.org?.navn;
  useEffect(() => {
    if (!profNavn) return;
    try {
      const key = "ba_recent_companies";
      const prev = JSON.parse(localStorage.getItem(key) || "[]");
      const entry = { orgnr, navn: String(profNavn) };
      const updated = [entry, ...prev.filter((c: { orgnr: string }) => c.orgnr !== orgnr)].slice(0, 10);
      localStorage.setItem(key, JSON.stringify(updated));
    } catch { /* ignore */ }
  }, [orgnr, profNavn]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!prof) {
    return (
      <div className="broker-card text-center text-sm text-muted-foreground">
        {T("Selskapet ble ikke funnet.")}{" "}
        <Link href="/search" className="text-primary underline">{T("Tilbake")}</Link>
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
    { label: T("Datainnhenting"),   desc: T("Selskapsdata fra BRREG"),            done: true },
    { label: T("Risikovurdering"),  desc: T("Risikoscore og AI-narrativ"),         done: risk.score != null },
    { label: T("Behovsanalyse"),    desc: T("Forsikringsbehov estimert"),          done: false },
    { label: T("Tilbud innhentet"), desc: T("Tilbud fra forsikringsselskaper"),    done: submissions.some((s) => s.status === "quoted") },
    { label: T("Tilbudsanalyse"),   desc: T("AI-sammenligning fullført"),          done: recommendations.length > 0 },
    { label: T("Presentasjon"),     desc: T("Forsikringstilbud PDF generert"),     done: false },
    { label: T("Kontrakt"),         desc: T("Tjenesteavtale signert i Avtaler"),   done: hasContract },
  ];

  const triggerCls =
    "data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-none text-muted-foreground hover:bg-muted px-4 py-2 text-sm font-medium rounded-lg";

  // Status chips — quick-glance state matching mockup 10.57.26
  // (megler-bilder polish §3a). Reads already-loaded data so no extra calls.
  const pepHits = Number((pep as Record<string, unknown>)?.hit_count ?? 0);
  const tilbudSendt = submissions.some((s) => s.status === "quoted");
  const riskScore = typeof risk.score === "number" ? risk.score : null;
  const riskBand = riskScore != null ? bandFor(riskScore) : null;
  const riskScoreClass = riskBand ? bandTailwindClass(riskBand.label) : "bg-muted text-muted-foreground";

  const tabBadgeCls = "ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-muted-foreground/15 text-muted-foreground data-[state=active]:bg-primary-foreground/20 data-[state=active]:text-primary-foreground";

  // Tab counts derived from already-loaded SWR data
  const okonomiCount = history.length;
  const forsikringCount = submissions.length;

  return (
    <div className="space-y-5">
      {/* Back link */}
      <Link
        href="/search"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="w-4 h-4" />
        {T("Tilbake til søk")}
      </Link>

      {/* Company header — status chips first (mockup 10.57.26), then name +
          industry, then action buttons. Status chips read from already-loaded
          SWR data so they're free. */}
      <div className="broker-card">
        {(tilbudSendt || riskScore != null || pepHits > 0) && (
          <div className="flex flex-wrap items-center gap-2 mb-3">
            {tilbudSendt && (
              <span className="inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-full bg-blue-100 text-blue-700">
                {T("Tilbud sendt")}
              </span>
            )}
            {riskScore != null && riskBand && (
              <span className={`inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-full ${riskScoreClass}`}>
                {T("Risiko")} {riskScore}/20 · {T(riskBand.label)}
              </span>
            )}
            {pepHits > 0 && (
              <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-amber-100 text-amber-800">
                <AlertTriangle className="w-3 h-3" />
                {pepHits} {T("PEP-treff")}
              </span>
            )}
          </div>
        )}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
          <div className="min-w-0">
            <h1 className="text-lg sm:text-xl font-bold text-foreground break-words">
              {String(org.navn ?? orgnr)}
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground mt-1 break-words">
              {orgnr}
              {!!org.organisasjonsform && ` · ${String(org.organisasjonsform)}`}
              {!!org.naeringskode1_beskrivelse && ` · ${String(org.naeringskode1_beskrivelse)}`}
            </p>
          </div>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
            <RiskBadge score={risk.score as number | undefined} className="self-start text-sm px-3 py-1" />
            <AnbudPackageButton orgnr={orgnr} />
          </div>
        </div>
      </div>

      {/* Workflow stepper */}
      <WorkflowStepper steps={steps} />

      {/* Tab navigation + content */}
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as typeof activeTab)}
        className="space-y-5"
      >
        <TabsList className="flex-wrap justify-start bg-transparent p-0 h-auto gap-2">
          <TabsTrigger value="oversikt"   className={triggerCls}>{T("Oversikt")}</TabsTrigger>
          <TabsTrigger value="okonomi"    className={triggerCls}>
            {T("Økonomi")}
            {okonomiCount > 0 && <span className={tabBadgeCls}>{okonomiCount}</span>}
          </TabsTrigger>
          <TabsTrigger value="forsikring" className={triggerCls}>
            {T("Forsikring")}
            {forsikringCount > 0 && <span className={tabBadgeCls}>{forsikringCount}</span>}
          </TabsTrigger>
          <TabsTrigger value="crm"        className={triggerCls}>{T("CRM")}</TabsTrigger>
          <TabsTrigger value="notater"    className={triggerCls}>{T("Notater")}</TabsTrigger>
          <TabsTrigger value="chat"       className={triggerCls}>{T("Chat")}</TabsTrigger>
          <TabsTrigger value="fokus"      className={triggerCls}>{T("Fokus")}</TabsTrigger>
          <TabsTrigger value="nyheter"    className={triggerCls}>{T("Nyheter")}</TabsTrigger>
        </TabsList>

        {/* ── Oversikt ─────────────────────────────────────────────────── */}
        <TabsContent value="oversikt" className="mt-0 focus-visible:ring-0">
          <OverviewTab
            orgnr={orgnr}
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
            struktur={strukturData}
          />
        </TabsContent>

        {/* ── Økonomi ─────────────────────────────────────────────────── */}
        <TabsContent value="okonomi" className="mt-0 focus-visible:ring-0">
          <FinancialsTab
            orgnr={orgnr}
            regn={regn as Record<string, unknown>}
            equityRatio={risk.equity_ratio}
            history={history}
            historyLoading={historyLoading}
            onHistoryRefetch={() => mutateHistory()}
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
        </TabsContent>

        {/* ── Forsikring ──────────────────────────────────────────────── */}
        <TabsContent value="forsikring" className="mt-0 focus-visible:ring-0">
          <div className="space-y-6">
            <PremiumBenchmark
              revenue={(prof?.regnskap?.revenue as number | undefined) ?? undefined}
              naceSection={(prof?.org?.naeringskode1 as string | undefined) ?? undefined}
            />
            <CoverageSection orgnr={orgnr} />
            <PropertySection orgnr={orgnr} />
            <ForsikringSection orgnr={orgnr} />
          </div>
        </TabsContent>

        {/* ── CRM ─────────────────────────────────────────────────────── */}
        <TabsContent value="crm" className="mt-0 focus-visible:ring-0">
          <div className="space-y-4">
            <div className="flex gap-2 flex-wrap">
              <Link href={`/idd?orgnr=${orgnr}`}
                className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-primary bg-accent hover:bg-accent">
                <FileText className="w-3.5 h-3.5" />
                {T("IDD behovsanalyse")}
              </Link>
              <button
                onClick={() => downloadCertificatePdf(orgnr)}
                className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-primary bg-accent hover:bg-accent"
              >
                <Download className="w-3.5 h-3.5" />
                {T("Last ned forsikringsbevis")}
              </button>
            </div>
            {policiesLoading && !policies ? (
              <div className="space-y-4" aria-busy="true" aria-live="polite">
                <Skeleton className="h-24 rounded-lg" />
                <Skeleton className="h-32 rounded-lg" />
                <Skeleton className="h-24 rounded-lg" />
              </div>
            ) : (
              <>
                <ContactsSection orgnr={orgnr} />
                <PoliciesSection orgnr={orgnr} />
                <SubmissionsSection orgnr={orgnr} />
                <RecommendationsSection orgnr={orgnr} />
                <ClaimsSection orgnr={orgnr} policies={policies ?? []} />
                <ActivitiesSection orgnr={orgnr} />
                <ClientPortalSection orgnr={orgnr} />
              </>
            )}
          </div>
        </TabsContent>

        {/* ── Notater ──────────────────────────────────────────────────── */}
        <TabsContent value="notater" className="mt-0 focus-visible:ring-0">
          <NotaterSection orgnr={orgnr} />
        </TabsContent>

        {/* ── Chat ─────────────────────────────────────────────────────── */}
        <TabsContent value="chat" className="mt-0 focus-visible:ring-0">
          <OrgChatSection orgnr={orgnr} orgName={String(org.navn ?? orgnr)} />
        </TabsContent>

        {/* ── Nyheter ──────────────────────────────────────────────────── */}
        <TabsContent value="nyheter" className="mt-0 focus-visible:ring-0">
          <NewsTab orgnr={orgnr} />
        </TabsContent>

        {/* ── Fokus-whiteboard ─────────────────────────────────────────── */}
        <TabsContent value="fokus" className="mt-0 focus-visible:ring-0">
          <WhiteboardTab
            orgnr={orgnr}
            orgName={String(org.navn ?? orgnr)}
            suggestedFacts={buildSuggestedFacts({
              org,
              regn,
              risk,
              benchmark,
            })}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/**
 * Pull one-line summary facts from the various data sources the page has
 * already loaded, so the Fokus tab can offer them as one-click "add to
 * whiteboard" chips instead of forcing the broker to retype each value.
 */
function buildSuggestedFacts({
  org,
  regn,
  risk,
  benchmark,
}: {
  org: Record<string, unknown>;
  regn: Record<string, unknown>;
  risk: {
    score?: number;
    altman_z?: {
      z_score: number;
      zone: "safe" | "grey" | "distress";
      score_20: number;
    } | null;
  };
  benchmark: Record<string, unknown> | null | undefined;
}): { label: string; value: string; source_tab: string }[] {
  const facts: { label: string; value: string; source_tab: string }[] = [];
  if (org?.navn) facts.push({ label: "Selskap", value: String(org.navn), source_tab: "Oversikt" });
  if (org?.naeringskode1_beskrivelse) {
    facts.push({
      label: "Bransje",
      value: String(org.naeringskode1_beskrivelse),
      source_tab: "Oversikt",
    });
  }
  if (typeof risk?.score === "number") {
    facts.push({ label: "Risikoscore", value: `${risk.score}/20`, source_tab: "Oversikt" });
  }
  // Altman Z″ chip — only surfaces when the model could compute it
  // (non-financial companies). Banks/insurers get risk.altman_z === null
  // and we skip the chip rather than flashing "N/A" in the broker's face.
  if (risk?.altman_z) {
    const zoneLabel =
      risk.altman_z.zone === "safe"
        ? "trygg sone"
        : risk.altman_z.zone === "grey"
          ? "gråsone"
          : "nødsone";
    facts.push({
      label: "Altman Z″",
      value: `${risk.altman_z.z_score.toFixed(2)} (${zoneLabel})`,
      source_tab: "Oversikt",
    });
  }
  const rev = regn?.sumDriftsinntekter ?? regn?.sum_driftsinntekter;
  if (typeof rev === "number") {
    facts.push({
      label: "Omsetning",
      value: `${(rev / 1_000_000).toFixed(1)} MNOK`,
      source_tab: "Økonomi",
    });
  }
  const eq = regn?.sumEgenkapital ?? regn?.sum_egenkapital;
  if (typeof eq === "number") {
    facts.push({
      label: "Egenkapital",
      value: `${(eq / 1_000_000).toFixed(1)} MNOK`,
      source_tab: "Økonomi",
    });
  }
  const benchmarkObj = (benchmark ?? {}) as Record<string, unknown>;
  const bench = benchmarkObj.benchmark as Record<string, unknown> | undefined;
  if (bench && typeof bench.industry === "string") {
    facts.push({
      label: "Bransje-sammenligning",
      value: bench.industry as string,
      source_tab: "Oversikt",
    });
  }
  return facts;
}
