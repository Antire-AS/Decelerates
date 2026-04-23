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
import { InboundEmailSection } from "@/components/admin/InboundEmailSection";
import { useT } from "@/lib/i18n";

const STAT_KEYS: Record<string, string> = {
  companies: "Selskaper",
  policies: "Aktive avtaler",
  documents: "Dokumenter",
  sla_agreements: "SLA-avtaler",
  activities: "Aktiviteter",
  renewals_30d: "Fornyelser (30d)",
};

// ── Data controls (kept inline — coordinates many API actions) ────────────────

function DataControlsSection() {
  const T = useT();
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
            .join(" · ") || T("Fullført.")
        : T("Fullført.");
      setMessages((m) => ({ ...m, [key]: `✅ ${text}` }));
    } catch (e) { setMessages((m) => ({ ...m, [key]: `${T("Feil")}: ${String(e)}` })); }
    finally { setLoading(null); }
  }

  return (
    <div className="space-y-3">
      {/* CRM demo seed */}
      <div className="broker-card">
        <SectionHeader
          title={T("CRM demo-data")}
          subtitle={T("Oppretter realistiske forsikringsavtaler, skader og aktiviteter for demo-selskapene.")}
        />
        <div className="flex flex-wrap gap-3">
          <ActionButton
            label={T("Seed fiktive selskaper (full demo)")} loadingLabel={T("Seeder…")}
            disabled={loading === "fulldemo"}
            onClick={() => run("fulldemo", seedFullDemo)}
          />
          <ActionButton
            label={T("Seed CRM demo-data")} loadingLabel={T("Seeder…")}
            disabled={loading === "crm"}
            onClick={() => run("crm", seedCrmDemo)}
          />
        </div>
        <ResultMessage msg={messages.fulldemo ?? null} />
        <ResultMessage msg={messages.crm ?? null} />
      </div>

      {/* Demo documents */}
      <div className="broker-card">
        <SectionHeader
          title={T("Demo-dokumenter")}
          subtitle={T("Genererer anonymiserte kopier av eksisterende forsikringsdokumenter for testmiljø.")}
        />
        <ActionButton
          label={T("Generer demo-dokumenter")} loadingLabel={T("Genererer…")}
          variant="secondary"
          disabled={loading === "docs"}
          onClick={() => run("docs", seedDemoDocuments)}
        />
        <ResultMessage msg={messages.docs ?? null} />
      </div>

      {/* Load demo / Reset */}
      <div className="broker-card">
        <SectionHeader title={T("Datahåndtering")} />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-medium text-foreground mb-1">{T("Last inn demo-data")}</p>
            <p className="text-xs text-muted-foreground mb-2">
              {T("Oppretter 'Demo Portefølje' med 8 store norske selskaper og starter PDF-ekstraksjon.")}
            </p>
            <ActionButton
              label={T("▶ Last inn demo")} loadingLabel={T("Henter…")}
              disabled={loading === "demo"}
              onClick={() => run("demo", loadDemo)}
            />
            <ResultMessage msg={messages.demo ?? null} />
          </div>
          <div>
            <p className="text-xs font-medium text-foreground mb-1">{T("Nullstill innsamlet data")}</p>
            <p className="text-xs text-muted-foreground mb-2">
              {T("Sletter selskapsdata og regnskapshistorikk. Videoer og dokumenter beholdes.")}
            </p>
            {!confirmReset ? (
              <ActionButton label={T("🔄 Nullstill data")} variant="secondary" onClick={() => setConfirmReset(true)} />
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-red-600 font-medium">
                  {T("⚠️ Sletter alle selskaper og regnskapsdata. Er du sikker?")}
                </p>
                <div className="flex gap-2">
                  <ActionButton
                    label={T("Ja, nullstill")} loadingLabel={T("Nullstiller…")}
                    variant="danger"
                    disabled={loading === "reset"}
                    onClick={async () => {
                      await run("reset", resetData);
                      setConfirmReset(false);
                    }}
                  />
                  <ActionButton label={T("Avbryt")} variant="secondary" onClick={() => setConfirmReset(false)} />
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
          title={T("🇳🇴 Norges Topp 100")}
          subtitle={T("Slår opp ~100 største norske selskaper i BRREG og starter AI-agent for årsrapport-PDF. Tar 30–90 minutter.")}
        />
        <ActionButton
          label={T("🚀 Hent finansdata for Norges Topp 100")} loadingLabel={T("Starter…")}
          disabled={loading === "top100"}
          onClick={() => run("top100", seedNorwayTop100)}
        />
        <ResultMessage msg={messages.top100 ?? null} />
      </div>

      {/* Email notifications */}
      <div className="broker-card">
        <SectionHeader title={T("📧 E-postvarsler")} subtitle={T("Manuell utsendelse av automatiske varsler.")} />
        <div className="space-y-3">
          <div>
            <p className="text-xs font-medium text-foreground mb-0.5">{T("Porteføljedigest")}</p>
            <p className="text-xs text-muted-foreground mb-1">{T("Sender e-post med aktive vekstalerts på tvers av alle porteføljer.")}</p>
            <ActionButton
              label={T("Send porteføljedigest")} loadingLabel={T("Sender…")}
              variant="secondary"
              disabled={loading === "digest"}
              onClick={() => run("digest", sendPortfolioDigest)}
            />
            <ResultMessage msg={messages.digest ?? null} />
          </div>
          <div>
            <p className="text-xs font-medium text-foreground mb-0.5">{T("Aktivitetspåminnelser")}</p>
            <p className="text-xs text-muted-foreground mb-1">{T("Varsler om forfallne og forfalldagsoppgaver.")}</p>
            <ActionButton
              label={T("Send aktivitetspåminnelser")} loadingLabel={T("Sjekker…")}
              variant="secondary"
              disabled={loading === "reminders"}
              onClick={() => run("reminders", sendActivityReminders)}
            />
            <ResultMessage msg={messages.reminders ?? null} />
          </div>
          <div>
            <p className="text-xs font-medium text-foreground mb-0.5">{T("Fornyelsesterskelvarsler (90/60/30 dager)")}</p>
            <p className="text-xs text-muted-foreground mb-1">{T("Sender målrettede e-poster per terskel. Idempotent — trygt å kjøre fra cron.")}</p>
            <ActionButton
              label={T("Send fornyelsesterskelvarsler")} loadingLabel={T("Sjekker…")}
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
  const T = useT();
  const { data: rawStats, isLoading } = useSWR("admin-stats", getAdminStats);
  const stats = rawStats as Record<string, unknown> | undefined;
  const statEntries = stats ? Object.entries(stats).filter(([k]) => k in STAT_KEYS) : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{T("Admin")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {T("Systemstatistikk, brukeradministrasjon og dataverktøy")}
        </p>
      </div>

      {/* Stats grid */}
      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="broker-card h-20 animate-pulse bg-muted" />
          ))}
        </div>
      )}
      {!isLoading && statEntries.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {statEntries.map(([key, value]) => (
            <div key={key} className="broker-card">
              <p className="text-xs text-muted-foreground font-medium mb-1">{STAT_KEYS[key] ? T(STAT_KEYS[key]) : key}</p>
              <p className="text-2xl font-bold text-foreground">
                {typeof value === "number" ? value : String(value ?? "–")}
              </p>
            </div>
          ))}
        </div>
      )}

      <UsersSection />
      <ExportsSection />
      <DataControlsSection />
      <InboundEmailSection />
      <AuditLogSection />
    </div>
  );
}
