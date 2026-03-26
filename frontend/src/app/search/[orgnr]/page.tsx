"use client";

import { use, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  getOrgProfile, getSlaAgreements, getOrgPolicies,
  type OrgProfile,
} from "@/lib/api";
import RiskBadge from "@/components/company/RiskBadge";
import WorkflowStepper, { type WorkflowStep } from "@/components/company/WorkflowStepper";
import ContactsSection from "@/components/crm/ContactsSection";
import PoliciesSection from "@/components/crm/PoliciesSection";
import ClaimsSection from "@/components/crm/ClaimsSection";
import ActivitiesSection from "@/components/crm/ActivitiesSection";
import ForsikringSection from "@/components/crm/ForsikringSection";
import { ArrowLeft, Loader2, ExternalLink, AlertTriangle } from "lucide-react";


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

  const [activeTab, setActiveTab] = useState<"oversikt" | "okonomi" | "forsikring" | "crm">(
    "oversikt",
  );

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
        {(["oversikt", "okonomi", "forsikring", "crm"] as const).map((t) => (
          <button key={t} onClick={() => setActiveTab(t)} className={TAB_CLS(t)}>
            {t === "oversikt"   ? "Oversikt"   :
             t === "okonomi"    ? "Økonomi"    :
             t === "forsikring" ? "Forsikring" : "CRM"}
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
        </div>
      )}

      {/* ── Økonomi ─────────────────────────────────────────────────── */}
      {activeTab === "okonomi" && (
        <div className="space-y-4">
          <Section title="Regnskap">
            {Object.keys(regn).length === 0 ? (
              <p className="text-sm text-[#8A7F74]">
                Ingen regnskapsdata tilgjengelig fra Regnskapsregisteret.
                Last opp årsrapport-PDF i Forsikring-fanen for å hente tall.
              </p>
            ) : (
              <div className="space-y-1">
                {Object.entries(regn).map(([k, v]) => (
                  <KV key={k} label={k} value={v} />
                ))}
              </div>
            )}
          </Section>
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
    </div>
  );
}
