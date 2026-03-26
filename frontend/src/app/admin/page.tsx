"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getAdminStats, getUsers, updateUserRole, getAuditLog,
  getRenewals, getPolicies,
  seedCrmDemo, seedDemoDocuments, seedFullDemo, loadDemo, resetData, seedNorwayTop100,
  sendPortfolioDigest, sendActivityReminders, sendRenewalThresholdEmails,
  type User,
} from "@/lib/api";
import { Loader2, RefreshCw, Download } from "lucide-react";

const ROLES = ["admin", "broker", "viewer"] as const;

const STAT_LABELS: Record<string, string> = {
  companies: "Selskaper",
  policies: "Aktive avtaler",
  documents: "Dokumenter",
  sla_agreements: "SLA-avtaler",
  activities: "Aktiviteter",
  renewals_30d: "Fornyelser (30d)",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-sm font-semibold text-[#2C3E50]">{title}</h2>
      {subtitle && <p className="text-xs text-[#8A7F74] mt-0.5">{subtitle}</p>}
    </div>
  );
}

function ActionButton({
  label, loadingLabel, onClick, variant = "primary", disabled,
}: {
  label: string; loadingLabel?: string; onClick: () => void;
  variant?: "primary" | "secondary" | "danger"; disabled?: boolean;
}) {
  const base = "px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const styles = {
    primary:   `${base} bg-[#2C3E50] text-white hover:bg-[#3d5166]`,
    secondary: `${base} border border-[#D4C9B8] text-[#2C3E50] hover:bg-[#EDE8E3]`,
    danger:    `${base} bg-red-600 text-white hover:bg-red-700`,
  };
  return (
    <button onClick={onClick} disabled={disabled} className={styles[variant]}>
      {disabled && loadingLabel ? loadingLabel : label}
    </button>
  );
}

function ResultMessage({ msg }: { msg: string | null }) {
  if (!msg) return null;
  const isErr = msg.startsWith("Feil");
  return (
    <p className={`mt-2 text-xs ${isErr ? "text-red-600" : "text-green-700"}`}>{msg}</p>
  );
}

// ── Sections ──────────────────────────────────────────────────────────────────

function UsersSection() {
  const { data: users, isLoading } = useSWR<User[]>("users", getUsers);
  const [pendingRoles, setPendingRoles] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function handleSave(u: User) {
    const newRole = pendingRoles[u.id] ?? u.role;
    if (newRole === u.role) { setMsg("Ingen endring."); return; }
    setSaving(u.id); setMsg(null);
    try {
      await updateUserRole(u.id, newRole);
      setMsg(`Rolle oppdatert til ${newRole}.`);
    } catch (e) { setMsg(`Feil: ${String(e)}`); }
    finally { setSaving(null); }
  }

  return (
    <div className="broker-card">
      <SectionHeader
        title="Brukere og tilganger"
        subtitle={users ? `${users.length} brukere i firmaet` : undefined}
      />
      {isLoading && <Loader2 className="w-5 h-5 animate-spin text-[#4A6FA5]" />}
      {!isLoading && !users?.length && (
        <p className="text-xs text-[#8A7F74]">Ingen brukere funnet.</p>
      )}
      {users && users.length > 0 && (
        <div className="divide-y divide-[#EDE8E3]">
          <div className="grid grid-cols-[3fr_4fr_2fr_auto] gap-3 py-2 text-xs font-semibold text-[#8A7F74]">
            <span>Navn</span><span>E-post</span><span>Rolle</span><span />
          </div>
          {users.map((u) => (
            <div key={u.id} className="grid grid-cols-[3fr_4fr_2fr_auto] gap-3 py-2.5 items-center">
              <span className="text-sm text-[#2C3E50]">{u.name ?? "–"}</span>
              <span className="text-xs text-[#8A7F74]">{u.email}</span>
              <select
                value={pendingRoles[u.id] ?? u.role}
                onChange={(e) => setPendingRoles((p) => ({ ...p, [u.id]: e.target.value }))}
                className="text-xs border border-[#D4C9B8] rounded px-1.5 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
              >
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <button
                onClick={() => handleSave(u)}
                disabled={saving === u.id}
                className="text-xs px-2.5 py-1 rounded bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50"
              >
                {saving === u.id ? "…" : "Lagre"}
              </button>
            </div>
          ))}
        </div>
      )}
      <ResultMessage msg={msg} />
    </div>
  );
}

function ExportsSection() {
  const [loadingRenewals, setLoadingRenewals] = useState(false);
  const [loadingPolicies, setLoadingPolicies] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function downloadCsv(rows: Record<string, unknown>[], filename: string) {
    if (!rows.length) { setMsg("Ingen data funnet."); return; }
    const headers = Object.keys(rows[0]);
    const csv = [
      headers.join(","),
      ...rows.map((r) =>
        headers.map((h) => JSON.stringify(r[h] ?? "")).join(",")
      ),
    ].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" }));
    a.download = filename;
    a.click();
  }

  async function handleRenewals() {
    setLoadingRenewals(true); setMsg(null);
    try {
      const data = await getRenewals(365);
      await downloadCsv(data.map((r) => ({
        Orgnr: r.orgnr, Klient: r.client_name, Forsikringsselskap: r.insurer,
        Produkt: r.insurance_type, "Premie (kr)": r.premium,
        Fornyelsesdato: r.renewal_date, "Dager igjen": r.days_until_renewal, Status: r.status,
      })), `fornyelser_${new Date().toISOString().slice(0, 10)}.csv`);
    } catch (e) { setMsg(`Feil: ${String(e)}`); }
    finally { setLoadingRenewals(false); }
  }

  async function handlePolicies() {
    setLoadingPolicies(true); setMsg(null);
    try {
      const data = await getPolicies();
      await downloadCsv(data.map((p) => ({
        Orgnr: p.orgnr, Forsikringsselskap: p.insurer, Produkt: p.product_type ?? "",
        Avtalenr: p.policy_number ?? "", "Premie (kr)": p.annual_premium_nok ?? "",
        "Forsikringssum (kr)": p.coverage_amount_nok ?? "",
        Startdato: p.start_date ?? "", Fornyelsesdato: p.renewal_date ?? "", Status: p.status,
      })), `avtaleoversikt_${new Date().toISOString().slice(0, 10)}.csv`);
    } catch (e) { setMsg(`Feil: ${String(e)}`); }
    finally { setLoadingPolicies(false); }
  }

  return (
    <div className="broker-card">
      <SectionHeader title="Eksporter data" />
      <div className="flex gap-3 flex-wrap">
        <button
          onClick={handleRenewals}
          disabled={loadingRenewals}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#2C3E50] hover:bg-[#EDE8E3] disabled:opacity-50"
        >
          {loadingRenewals ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
          Fornyelsesrapport (CSV)
        </button>
        <button
          onClick={handlePolicies}
          disabled={loadingPolicies}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#2C3E50] hover:bg-[#EDE8E3] disabled:opacity-50"
        >
          {loadingPolicies ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
          Avtaleoversikt (CSV)
        </button>
      </div>
      <ResultMessage msg={msg} />
    </div>
  );
}

function AuditLogSection() {
  const [limit, setLimit] = useState(50);
  const { data: rows, isLoading, mutate } = useSWR<Record<string, unknown>[]>(
    `audit-${limit}`, () => getAuditLog(limit) as Promise<Record<string, unknown>[]>,
  );

  function downloadCsv() {
    if (!rows?.length) return;
    const hdrs = ["Tidspunkt", "Bruker", "Handling", "Orgnr", "Detaljer"];
    const csv = [
      hdrs.join(","),
      ...rows.map((r) => [
        JSON.stringify((String(r.created_at ?? "")).slice(0, 19).replace("T", " ")),
        JSON.stringify(r.actor_email ?? "–"),
        JSON.stringify(r.action ?? "–"),
        JSON.stringify(r.orgnr ?? "–"),
        JSON.stringify(r.detail ?? "–"),
      ].join(",")),
    ].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" }));
    a.download = `aktivitetslogg_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  }

  const unique_users   = new Set(rows?.map((r) => r.actor_email).filter(Boolean)).size;
  const unique_orgnrs  = new Set(rows?.map((r) => r.orgnr).filter(Boolean)).size;

  return (
    <div className="broker-card">
      <div className="flex items-center justify-between mb-3">
        <SectionHeader title="Aktivitetslogg" subtitle="Hvem har brukt applikasjonen og hvilke handlinger de har utført." />
        <div className="flex items-center gap-2">
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="text-xs border border-[#D4C9B8] rounded px-2 py-1 bg-white focus:outline-none"
          >
            {[10, 25, 50, 100, 200].map((v) => <option key={v} value={v}>{v} rader</option>)}
          </select>
          <button onClick={() => mutate()} className="text-[#8A7F74] hover:text-[#2C3E50]">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {rows && rows.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-3">
          {[
            { label: "Oppføringer", value: rows.length },
            { label: "Unike brukere", value: unique_users },
            { label: "Unike selskaper", value: unique_orgnrs },
          ].map(({ label, value }) => (
            <div key={label} className="bg-[#F9F7F4] rounded-lg p-3">
              <p className="text-xs text-[#8A7F74]">{label}</p>
              <p className="text-xl font-bold text-[#2C3E50]">{value}</p>
            </div>
          ))}
        </div>
      )}

      {isLoading && <Loader2 className="w-5 h-5 animate-spin text-[#4A6FA5]" />}
      {!isLoading && !rows?.length && (
        <p className="text-xs text-[#8A7F74]">Ingen aktivitet registrert ennå.</p>
      )}
      {rows && rows.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#EDE8E3]">
                  {["Tidspunkt", "Bruker", "Handling", "Orgnr", "Detaljer"].map((h) => (
                    <th key={h} className="text-left py-2 pr-3 text-[#8A7F74] font-semibold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EDE8E3]">
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-3 whitespace-nowrap text-[#8A7F74]">
                      {String(r.created_at ?? "").slice(0, 19).replace("T", " ")}
                    </td>
                    <td className="py-2 pr-3 text-[#2C3E50]">{String(r.actor_email ?? "–")}</td>
                    <td className="py-2 pr-3 text-[#2C3E50]">{String(r.action ?? "–")}</td>
                    <td className="py-2 pr-3 text-[#8A7F74]">{String(r.orgnr ?? "–")}</td>
                    <td className="py-2 pr-3 text-[#8A7F74] max-w-xs truncate">{String(r.detail ?? "–")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            onClick={downloadCsv}
            className="mt-3 flex items-center gap-1.5 text-xs text-[#4A6FA5] hover:underline"
          >
            <Download className="w-3 h-3" /> Eksporter CSV
          </button>
        </>
      )}
    </div>
  );
}

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
