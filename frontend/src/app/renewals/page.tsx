"use client";

import { Fragment, useState } from "react";
import useSWR from "swr";
import { getRenewals, advanceRenewalStage, type Renewal } from "@/lib/api";
import { fmt, fmtDate } from "@/lib/format";
import { downloadXlsx } from "@/lib/excel-export";
import { Download, Sparkles, Mail } from "lucide-react";

function urgencyClass(days: number) {
  if (days <= 14) return "bg-red-100 text-red-700";
  if (days <= 30) return "bg-amber-100 text-amber-700";
  return "bg-green-100 text-green-700";
}

const STAGES = [
  { id: "not_started",    label: "Ikke startet",    color: "bg-gray-100 text-gray-600" },
  { id: "ready_to_quote", label: "Klar for tilbud", color: "bg-blue-100 text-blue-700" },
  { id: "quoted",         label: "Tilbud sendt",    color: "bg-purple-100 text-purple-700" },
  { id: "accepted",       label: "Akseptert",       color: "bg-green-100 text-green-700" },
  { id: "declined",       label: "Avslått",         color: "bg-red-100 text-red-700" },
] as const;

type StageId = typeof STAGES[number]["id"];

function stageMeta(stageId?: string) {
  return STAGES.find((s) => s.id === stageId) ?? STAGES[0];
}

const DAYS_OPTIONS = [30, 60, 90, 180];

export default function RenewalsPage() {
  const [days, setDays] = useState(90);
  const [view, setView] = useState<"table" | "kanban">("table");
  const [stageFilter, setStageFilter] = useState<StageId | "all">("all");
  const [advancing, setAdvancing]       = useState<number | null>(null);
  const [notifyEmails, setNotifyEmails] = useState<Record<number, string>>({});

  const { data: renewals, isLoading, mutate } = useSWR<Renewal[]>(
    ["renewals", days],
    () => getRenewals(days),
  );

  async function handleAdvance(renewal: Renewal, newStage: StageId) {
    setAdvancing(renewal.id);
    const email = notifyEmails[renewal.id]?.trim() || undefined;
    try {
      await advanceRenewalStage(renewal.id, newStage, email);
      await mutate();
    } catch {
      // ignore
    } finally {
      setAdvancing(null);
    }
  }

  const filtered = stageFilter === "all"
    ? (renewals ?? [])
    : (renewals ?? []).filter((r) => (r.renewal_stage ?? "not_started") === stageFilter);

  const stageCounts = STAGES.map((s) => ({
    ...s,
    count: (renewals ?? []).filter((r) => (r.renewal_stage ?? "not_started") === s.id).length,
  }));

  const totalPremium = (renewals ?? []).reduce((s, r) => s + (r.annual_premium_nok ?? r.premium ?? 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-[#2C3E50]">Fornyelsespipeline</h1>
          <p className="text-sm text-[#8A7F74] mt-1">Kommende polisefornyelseringer som krever oppfølging</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => renewals?.length && downloadXlsx(renewals.map((r) => ({
              Orgnr: r.orgnr, Klient: r.client_name, Forsikringsgiver: r.insurer,
              Produkt: r.product_type ?? r.insurance_type, "Premie (kr)": r.annual_premium_nok ?? r.premium,
              Fornyelsesdato: r.renewal_date, "Dager igjen": r.days_until_renewal,
              Steg: r.renewal_stage ?? "not_started",
            })), `fornyelser_${new Date().toISOString().slice(0, 10)}.xlsx`)}
            disabled={!renewals?.length}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-[#D4C9B8] text-[#8A7F74] hover:bg-[#EDE8E3] disabled:opacity-40"
          >
            <Download className="w-3 h-3" /> Excel
          </button>
          {DAYS_OPTIONS.map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                days === d ? "bg-[#2C3E50] text-white" : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"
              }`}>{d}d</button>
          ))}
        </div>
      </div>

      {/* Summary metrics */}
      {!isLoading && renewals && renewals.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="broker-card col-span-2 md:col-span-1">
            <p className="text-xs text-[#8A7F74] font-medium mb-1">Totalt</p>
            <p className="text-xl font-bold text-[#2C3E50]">{renewals.length}</p>
            <p className="text-xs text-[#8A7F74]">kr {fmt(totalPremium)}</p>
          </div>
          {stageCounts.map((s) => (
            <button key={s.id} onClick={() => setStageFilter(stageFilter === s.id ? "all" : s.id)}
              className={`broker-card text-left transition-all ${stageFilter === s.id ? "ring-2 ring-[#4A6FA5]" : ""}`}>
              <p className="text-xs text-[#8A7F74] font-medium mb-1 truncate">{s.label}</p>
              <p className="text-xl font-bold text-[#2C3E50]">{s.count}</p>
            </button>
          ))}
        </div>
      )}

      {/* View toggle */}
      {!isLoading && renewals && renewals.length > 0 && (
        <div className="flex gap-2">
          <button onClick={() => setView("table")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${view === "table" ? "bg-[#2C3E50] text-white" : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"}`}>
            Tabell
          </button>
          <button onClick={() => setView("kanban")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${view === "kanban" ? "bg-[#2C3E50] text-white" : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"}`}>
            Pipeline
          </button>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="broker-card space-y-3">
          {[...Array(5)].map((_, i) => <div key={i} className="h-8 rounded animate-pulse bg-[#EDE8E3]" />)}
        </div>
      )}

      {/* Table view */}
      {!isLoading && view === "table" && filtered.length > 0 && (
        <div className="broker-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-2 font-medium">Klient</th>
                <th className="text-left pb-2 font-medium">Forsikringstype</th>
                <th className="text-left pb-2 font-medium">Forsikringsgiver</th>
                <th className="text-right pb-2 font-medium">Premie (kr)</th>
                <th className="text-right pb-2 font-medium">Tegnet</th>
                <th className="text-right pb-2 font-medium">Fornyelsesdato</th>
                <th className="text-right pb-2 font-medium">Dager igjen</th>
                <th className="text-center pb-2 font-medium">Steg</th>
                <th className="text-center pb-2 font-medium">Flytt</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {filtered.map((r) => {
                const stage = (r.renewal_stage ?? "not_started") as StageId;
                const meta = stageMeta(stage);
                const nextStages = STAGES.filter((s) => s.id !== stage);
                const hasBrief = !!r.renewal_brief;
                return (
                  <Fragment key={r.id}>
                    <tr className="hover:bg-[#F9F7F4]">
                      <td className="py-2">
                        <span className="font-medium text-[#2C3E50]">{r.client_name}</span>
                        <span className="block text-xs text-[#8A7F74]">{r.orgnr}</span>
                      </td>
                      <td className="py-2 text-[#2C3E50]">{r.product_type ?? r.insurance_type}</td>
                      <td className="py-2 text-[#8A7F74]">{r.insurer}</td>
                      <td className="py-2 text-right font-medium text-[#2C3E50]">
                        {fmt(r.annual_premium_nok ?? r.premium)}
                      </td>
                      <td className="py-2 text-right text-[#8A7F74]">
                        {r.start_date ? fmtDate(r.start_date) : "–"}
                      </td>
                      <td className="py-2 text-right text-[#8A7F74]">{fmtDate(r.renewal_date)}</td>
                      <td className="py-2 text-right">
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${urgencyClass(r.days_until_renewal)}`}>
                          {r.days_until_renewal}d
                        </span>
                      </td>
                      <td className="py-2 text-center">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${meta.color}`}>{meta.label}</span>
                      </td>
                      <td className="py-2 text-center">
                        <select
                          disabled={advancing === r.id}
                          value=""
                          onChange={(e) => e.target.value && handleAdvance(r, e.target.value as StageId)}
                          className="text-xs border border-[#EDE8E3] rounded-lg px-2 py-1 text-[#2C3E50] bg-white"
                        >
                          <option value="">Flytt…</option>
                          {nextStages.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                        </select>
                      </td>
                    </tr>
                    {hasBrief && (
                      <tr className="bg-[#F0F4FB]">
                        <td colSpan={9} className="px-4 py-2">
                          <div className="flex gap-4">
                            <div className="flex-1">
                              <div className="flex items-center gap-1.5 mb-1">
                                <Sparkles className="w-3 h-3 text-[#4A6FA5]" />
                                <span className="text-[10px] font-semibold text-[#4A6FA5] uppercase tracking-wide">AI Fornyelsesbriefing</span>
                              </div>
                              <p className="text-xs text-[#2C3E50] whitespace-pre-line">{r.renewal_brief}</p>
                            </div>
                            {r.renewal_email_draft && (
                              <div className="flex-1 border-l border-[#C5D8F0] pl-4">
                                <div className="flex items-center gap-1.5 mb-1">
                                  <Mail className="w-3 h-3 text-[#4A6FA5]" />
                                  <span className="text-[10px] font-semibold text-[#4A6FA5] uppercase tracking-wide">Utkast til klient-epost</span>
                                </div>
                                <p className="text-xs text-[#8A7F74] whitespace-pre-line">{r.renewal_email_draft}</p>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          <p className="text-xs text-[#8A7F74] mt-3">
            Viser {filtered.length} av {renewals?.length} fornyelse(r) innen {days} dager
          </p>
        </div>
      )}

      {/* Kanban / Pipeline view */}
      {!isLoading && view === "kanban" && (renewals?.length ?? 0) > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 overflow-x-auto">
          {STAGES.map((stage) => {
            const cards = (renewals ?? []).filter((r) => (r.renewal_stage ?? "not_started") === stage.id);
            return (
              <div key={stage.id} className="min-w-[200px]">
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${stage.color}`}>{stage.label}</span>
                  <span className="text-xs text-[#8A7F74]">{cards.length}</span>
                </div>
                <div className="space-y-2">
                  {cards.length === 0 && (
                    <div className="border-2 border-dashed border-[#EDE8E3] rounded-lg p-4 text-center text-xs text-[#8A7F74]">Tom</div>
                  )}
                  {cards.map((r) => {
                    const nextStages = STAGES.filter((s) => s.id !== stage.id);
                    return (
                      <div key={r.id} className="broker-card !p-3 space-y-2">
                        <div>
                          <p className="text-xs font-semibold text-[#2C3E50] leading-tight">{r.client_name}</p>
                          <p className="text-xs text-[#8A7F74]">{r.product_type ?? r.insurance_type}</p>
                        </div>
                        <div className="flex items-center justify-between">
                          <div className="text-xs text-[#8A7F74]">
                            {r.start_date && <p>Tegnet: {fmtDate(r.start_date)}</p>}
                            <p>Fornyes: {fmtDate(r.renewal_date)}</p>
                          </div>
                          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${urgencyClass(r.days_until_renewal)}`}>
                            {r.days_until_renewal}d
                          </span>
                        </div>
                        {r.annual_premium_nok != null && (
                          <p className="text-xs text-[#8A7F74]">kr {fmt(r.annual_premium_nok)}</p>
                        )}
                        <input
                          type="email"
                          placeholder="E-post varsling (valgfri)"
                          value={notifyEmails[r.id] ?? ""}
                          onChange={(e) => setNotifyEmails((prev) => ({ ...prev, [r.id]: e.target.value }))}
                          className="w-full text-xs border border-[#EDE8E3] rounded-lg px-2 py-1 text-[#2C3E50] bg-white focus:outline-none focus:border-[#4A6FA5]"
                        />
                        <select
                          disabled={advancing === r.id}
                          value=""
                          onChange={(e) => e.target.value && handleAdvance(r, e.target.value as StageId)}
                          className="w-full text-xs border border-[#EDE8E3] rounded-lg px-2 py-1 text-[#2C3E50] bg-white"
                        >
                          <option value="">Flytt til…</option>
                          {nextStages.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                        </select>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {!isLoading && renewals?.length === 0 && (
        <div className="broker-card text-center py-12">
          <p className="text-sm font-medium text-[#2C3E50]">Ingen kommende fornyelser</p>
          <p className="text-xs text-[#8A7F74] mt-1">Ingen avtaler forfaller innen de neste {days} dagene.</p>
        </div>
      )}
    </div>
  );
}
