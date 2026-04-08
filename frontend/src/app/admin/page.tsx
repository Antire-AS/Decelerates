"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getAdminStats,
  seedCrmDemo, seedDemoDocuments, seedFullDemo, loadDemo, resetData, seedNorwayTop100,
  sendPortfolioDigest, sendActivityReminders, sendRenewalThresholdEmails,
} from "@/lib/api";
import { SectionHeader, ActionButton, ResultMessage } from "@/components/admin/shared";
import { UsersSection } from "@/components/admin/UsersSection";
import { ExportsSection } from "@/components/admin/ExportsSection";
import { AuditLogSection } from "@/components/admin/AuditLogSection";

const STAT_LABELS: Record<string, string> = {
  companies: "Selskaper",
  policies: "Aktive avtaler",
  documents: "Dokumenter",
  sla_agreements: "SLA-avtaler",
  activities: "Aktiviteter",
  renewals_30d: "Fornyelser (30d)",
};

// ── Data controls (kept inline — coordinates many API actions) ────────────────

function DataControlsSection() {
  const [loading, setLoading] = useState<string | null>(null);
  const [messages, setMessages] = useState<Record<string, string>>({});
  const [confirmReset, setConfirmReset] = useState(false);

  async function run(key: string, fn: () => Promise<unknown>) {
    setLoading(key); setMessages((m) => ({ ...m, [key]: "" }));
    try {
      const res = await fn() as Record<string, unknown>;
      const text = res && typeof res === "object"
        ? Object.entries(res)
            .filter(([, v]) => v !== null && v !== undefined && typeof v !== "object")
            .map(([k, v]) => `${k}: ${v}`)
            .join(" · ") || "Fullført."
        : "Fullført.";
      setMessages((m) => ({ ...m, [key]: `✅ ${text}` }));
    } catch (e) { setMessages((m) => ({ ...m, [key]: `Feil: ${String(e)}` })); }
    finally { setLoading(null); }
  }

  return (
    <div className="space-y-3">
      {/* CRM demo seed */}
      <div className="broker-card">
        <SectionHeader
          title="CRM demo-data"
          subtitle="Oppretter realistiske forsikringsavtaler, skader og aktiviteter for demo-selskapene."
        />
        <ActionButton
          label="Seed fiktive selskaper (full demo)" loadingLabel="Seeder…"
          disabled={loading === "fulldemo"}
          onClick={() => run("fulldemo", seedFullDemo)}
        />
        <ResultMessage msg={messages.fulldemo ?? null} />
        <ActionButton
          label="Seed CRM demo-data" loadingLabel="Seeder…"
          disabled={loading === "crm"}
          onClick={() => run("crm", seedCrmDemo)}
        />
        <ResultMessage msg={messages.crm ?? null} />
      </div>

      {/* Demo documents */}
      <div className="broker-card">
        <SectionHeader
          title="Demo-dokumenter"
          subtitle="Genererer anonymiserte kopier av eksisterende forsikringsdokumenter for testmiljø."
        />
        <ActionButton
          label="Generer demo-dokumenter" loadingLabel="Genererer…"
          variant="secondary"
          disabled={loading === "docs"}
          onClick={() => run("docs", seedDemoDocuments)}
        />
        <ResultMessage msg={messages.docs ?? null} />
      </div>

      {/* Load demo / Reset */}
      <div className="broker-card">
        <SectionHeader title="Datahåndtering" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-medium text-[#2C3E50] mb-1">Last inn demo-data</p>
            <p className="text-xs text-[#8A7F74] mb-2">
              Oppretter &apos;Demo Portefølje&apos; med 8 store norske selskaper og starter PDF-ekstraksjon.
            </p>
            <ActionButton
              label="▶ Last inn demo" loadingLabel="Henter…"
              disabled={loading === "demo"}
              onClick={() => run("demo", loadDemo)}
            />
            <ResultMessage msg={messages.demo ?? null} />
          </div>
          <div>
            <p className="text-xs font-medium text-[#2C3E50] mb-1">Nullstill innsamlet data</p>
            <p className="text-xs text-[#8A7F74] mb-2">
              Sletter selskapsdata og regnskapshistorikk. Videoer og dokumenter beholdes.
            </p>
            {!confirmReset ? (
              <ActionButton label="🔄 Nullstill data" variant="secondary" onClick={() => setConfirmReset(true)} />
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-red-600 font-medium">
                  ⚠️ Sletter alle selskaper og regnskapsdata. Er du sikker?
                </p>
                <div className="flex gap-2">
                  <ActionButton
                    label="Ja, nullstill" loadingLabel="Nullstiller…"
                    variant="danger"
                    disabled={loading === "reset"}
                    onClick={async () => {
                      await run("reset", resetData);
                      setConfirmReset(false);
                    }}
                  />
                  <ActionButton label="Avbryt" variant="secondary" onClick={() => setConfirmReset(false)} />
                </div>
              </div>
            )}
            <ResultMessage msg={messages.reset ?? null} />
          </div>
        </div>
      </div>

      {/* Norway Top 100 */}
      <div className="broker-card">
        <SectionHeader
          title="🇳🇴 Norges Topp 100"
          subtitle="Slår opp ~100 største norske selskaper i BRREG og starter AI-agent for årsrapport-PDF. Tar 30–90 minutter."
        />
        <ActionButton
          label="🚀 Hent finansdata for Norges Topp 100" loadingLabel="Starter…"
          disabled={loading === "top100"}
          onClick={() => run("top100", seedNorwayTop100)}
        />
        <ResultMessage msg={messages.top100 ?? null} />
      </div>

      {/* Email notifications */}
      <div className="broker-card">
        <SectionHeader title="📧 E-postvarsler" subtitle="Manuell utsendelse av automatiske varsler." />
        <div className="space-y-3">
          <div>
            <p className="text-xs font-medium text-[#2C3E50] mb-0.5">Porteføljedigest</p>
            <p className="text-xs text-[#8A7F74] mb-1">Sender e-post med aktive vekstalerts på tvers av alle porteføljer.</p>
            <ActionButton
              label="Send porteføljedigest" loadingLabel="Sender…"
              variant="secondary"
              disabled={loading === "digest"}
              onClick={() => run("digest", sendPortfolioDigest)}
            />
            <ResultMessage msg={messages.digest ?? null} />
          </div>
          <div>
            <p className="text-xs font-medium text-[#2C3E50] mb-0.5">Aktivitetspåminnelser</p>
            <p className="text-xs text-[#8A7F74] mb-1">Varsler om forfallne og forfalldagsoppgaver.</p>
            <ActionButton
              label="Send aktivitetspåminnelser" loadingLabel="Sjekker…"
              variant="secondary"
              disabled={loading === "reminders"}
              onClick={() => run("reminders", sendActivityReminders)}
            />
            <ResultMessage msg={messages.reminders ?? null} />
          </div>
          <div>
            <p className="text-xs font-medium text-[#2C3E50] mb-0.5">Fornyelsesterskelvarsler (90/60/30 dager)</p>
            <p className="text-xs text-[#8A7F74] mb-1">Sender målrettede e-poster per terskel. Idempotent — trygt å kjøre fra cron.</p>
            <ActionButton
              label="Send fornyelsesterskelvarsler" loadingLabel="Sjekker…"
              variant="secondary"
              disabled={loading === "threshold"}
              onClick={() => run("threshold", sendRenewalThresholdEmails)}
            />
            <ResultMessage msg={messages.threshold ?? null} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { data: rawStats, isLoading } = useSWR("admin-stats", getAdminStats);
  const stats = rawStats as Record<string, unknown> | undefined;
  const statEntries = stats ? Object.entries(stats).filter(([k]) => k in STAT_LABELS) : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Admin</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          Systemstatistikk, brukeradministrasjon og dataverktøy
        </p>
      </div>

      {/* Stats grid */}
      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="broker-card h-20 animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}
      {!isLoading && statEntries.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {statEntries.map(([key, value]) => (
            <div key={key} className="broker-card">
              <p className="text-xs text-[#8A7F74] font-medium mb-1">{STAT_LABELS[key] ?? key}</p>
              <p className="text-2xl font-bold text-[#2C3E50]">
                {typeof value === "number" ? value : String(value ?? "–")}
              </p>
            </div>
          ))}
        </div>
      )}

      <UsersSection />
      <ExportsSection />
      <DataControlsSection />
      <AuditLogSection />
    </div>
  );
}
