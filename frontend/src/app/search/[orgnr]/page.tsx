"use client";

import { use, useState, Fragment } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import useSWR from "swr";
import {
  getOrgProfile, getSlaAgreements, getOrgPolicies, getOrgHistory,
  getOrgRoles, getOrgLicenses, getOrgBankruptcy, getOrgBenchmark,
  getOrgKoordinater,
  addOrgPdfHistory, getOrgExtractionStatus, getOrgFinancialCommentary,
  type OrgProfile, type HistoryRow,
} from "@/lib/api";

const CompanyMap = dynamic(() => import("@/components/company/CompanyMap"), { ssr: false });
import RiskBadge from "@/components/company/RiskBadge";
import WorkflowStepper, { type WorkflowStep } from "@/components/company/WorkflowStepper";
import ContactsSection from "@/components/crm/ContactsSection";
import PoliciesSection from "@/components/crm/PoliciesSection";
import ClaimsSection from "@/components/crm/ClaimsSection";
import ActivitiesSection from "@/components/crm/ActivitiesSection";
import ForsikringSection from "@/components/crm/ForsikringSection";
import NotaterSection from "@/components/company/NotaterSection";
import OrgChatSection from "@/components/company/OrgChatSection";
import { ArrowLeft, Loader2, ExternalLink, AlertTriangle, Shield, Users, TrendingUp, Link2, Sparkles, Info, ChevronDown, ChevronUp } from "lucide-react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";


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

function KV({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="flex justify-between text-sm gap-4">
      <span className="text-[#8A7F74]">{label}</span>
      <span className="text-[#2C3E50] font-medium text-right">{fmt(value)}</span>
    </div>
  );
}

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

  // Lazy-load financial history only when Økonomi tab is active
  const { data: historyData, isLoading: historyLoading } = useSWR<HistoryRow[]>(
    activeTab === "okonomi" ? `history-${orgnr}` : null,
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

  const org   = prof.org  ?? {};
  const regn  = prof.regnskap ?? {};
  const risk  = prof.risk ?? {};
  const pep   = prof.pep  ?? {};
  const rs    = prof.risk_summary ?? {};

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
        <div className="space-y-4">
          <Section title="Selskapsinfo">
            <KV label="Orgnr"     value={org.orgnr} />
            <KV label="Adresse"   value={org.forretningsadresse} />
            <KV label="Kommune"   value={org.kommune} />
            <KV label="Stiftet"   value={org.stiftelsesdato} />
            <KV label="Ansatte"   value={org.antallAnsatte} />
            {!!org.hjemmeside && (
              <div className="flex justify-between text-sm">
                <span className="text-[#8A7F74]">Nettsted</span>
                <a
                  href={String(org.hjemmeside)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#4A6FA5] flex items-center gap-1 hover:underline"
                >
                  {String(org.hjemmeside).replace(/^https?:\/\//, "").slice(0, 30)}
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            )}
          </Section>

          {/* Map */}
          {(() => {
            const coords = (koordinaterData as { coordinates?: { lat: number; lon: number } } | null)?.coordinates;
            return coords?.lat && coords?.lon ? (
              <Section title="Lokasjon">
                <CompanyMap lat={coords.lat} lon={coords.lon} label={String(org.navn ?? org.orgnr)} />
              </Section>
            ) : null;
          })()}

          <Section title="Risikoscore">
            <div className="flex items-center gap-3">
              <RiskBadge score={risk.score as number | undefined} className="text-sm px-3 py-1" />
              <span className="text-2xl font-bold text-[#2C3E50]">
                {risk.score ?? "–"}
                <span className="text-sm font-normal text-[#8A7F74]"> / 20</span>
              </span>
            </div>
            {Array.isArray(risk.reasons) && risk.reasons.length > 0 && (
              <ul className="space-y-1 mt-2">
                {(risk.reasons as string[]).map((r, i) => (
                  <li key={i} className="text-xs text-[#8A7F74] flex gap-2">
                    <span>•</span> {r}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          {/* Key financials summary */}
          {Object.keys(regn).length > 0 && (
            <Section title="Nøkkeltall">
              <KV label="Omsetning"    value={fmtMnok(regn.sumDriftsinntekter)} />
              <KV label="Nettoresultat" value={fmtMnok(regn.arsresultat)} />
              <KV label="Egenkapital"  value={fmtMnok(regn.sumEgenkapital)} />
              <KV label="Egenkapitalandel"
                value={risk.equity_ratio != null
                  ? `${(Number(risk.equity_ratio) * 100).toFixed(1)}%`
                  : "–"}
              />
            </Section>
          )}

          {/* Bankruptcy alert */}
          {!!bankruptcy && !!(bankruptcy.konkurs || bankruptcy.underAvvikling || bankruptcy.underTvangsavviklingEllerTvangsopplosning) && (
            <div className="broker-card border-l-4 border-red-500">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
                <span className="text-sm font-semibold text-red-700">
                  {bankruptcy.konkurs ? "Konkurs" : bankruptcy.underAvvikling ? "Under avvikling" : "Under tvangsavvikling/tvangsoppløsning"}
                </span>
              </div>
            </div>
          )}

          {/* PEP / sanctions */}
          {pep && (Object.keys(pep).length > 0) && (
            <Section title="PEP / sanksjonssjekk">
              <div className="flex items-start gap-2 text-sm">
                <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                <pre className="text-xs text-[#2C3E50] whitespace-pre-wrap overflow-auto max-h-40">
                  {JSON.stringify(pep, null, 2)}
                </pre>
              </div>
            </Section>
          )}

          {/* Board members */}
          {Array.isArray((roles as Record<string, unknown> | null)?.roller) && ((roles as Record<string, unknown>).roller as unknown[]).length > 0 && (
            <Section title="Styremedlemmer">
              <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
                <Users className="w-3.5 h-3.5" />
                <span>Fra Brønnøysundregistrene</span>
              </div>
              <div className="space-y-2">
                {((roles as Record<string, unknown>).roller as Record<string, unknown>[]).slice(0, 8).map((r, i) => {
                  const person = (r.person ?? r) as Record<string, unknown>;
                  const navn = [person.fornavn, person.etternavn].filter(Boolean).join(" ") || (r.navn as string) || "–";
                  const rolle = (r.rolle as Record<string, unknown>)?.beskrivelse ?? r.tittel ?? r.type ?? "";
                  return (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-[#2C3E50] font-medium">{navn}</span>
                      <span className="text-[#8A7F74] text-xs">{String(rolle)}</span>
                    </div>
                  );
                })}
              </div>
            </Section>
          )}

          {/* Finanstilsynet licenses */}
          {Array.isArray((licenses as Record<string, unknown> | null)?.licences) && ((licenses as Record<string, unknown>).licences as unknown[]).length > 0 && (
            <Section title="Finanstilsynet — konsesjoner">
              <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
                <Shield className="w-3.5 h-3.5" />
                <span>Registrerte finanskonsesjoner</span>
              </div>
              <div className="space-y-1.5">
                {((licenses as Record<string, unknown>).licences as Record<string, unknown>[]).slice(0, 6).map((l, i) => (
                  <div key={i} className="text-xs text-[#2C3E50] flex items-start gap-1.5">
                    <span className="text-[#C8A951] mt-0.5">•</span>
                    <span>{String(l.type ?? l.name ?? l.licence_type ?? JSON.stringify(l))}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Industry benchmark */}
          {benchmark && Object.keys(benchmark).length > 0 && (
            <Section title="SSB-bransjesammenligning">
              <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
                <TrendingUp className="w-3.5 h-3.5" />
                <span>Typiske nøkkeltall for bransjen</span>
              </div>
              {Object.entries(benchmark as Record<string, { low: number; high: number } | number | string>)
                .filter(([k]) => !["naeringskode", "beskrivelse", "source"].includes(k))
                .slice(0, 5)
                .map(([key, val]) => (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-[#8A7F74] capitalize">{key.replace(/_/g, " ")}</span>
                    <span className="text-[#2C3E50] font-medium text-xs">
                      {typeof val === "object" && val !== null && "low" in val
                        ? `${(val as { low: number; high: number }).low}–${(val as { low: number; high: number }).high}%`
                        : String(val)}
                    </span>
                  </div>
                ))}
            </Section>
          )}
        </div>
      )}

      {/* ── Økonomi ─────────────────────────────────────────────────── */}
      {activeTab === "okonomi" && (
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
