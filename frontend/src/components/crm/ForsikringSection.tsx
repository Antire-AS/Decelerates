"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getOrgInsuranceNeeds, generateRiskOffer, generateNarrative,
  getOrgOffers, updateOfferStatus, deleteOffer,
  type InsuranceNeed, type InsuranceOffer,
} from "@/lib/api";
import { Loader2, Trash2, ChevronDown, ChevronUp, Sparkles, FileText } from "lucide-react";

const PRIORITY_COLOR: Record<string, string> = {
  critical: "text-red-600", high: "text-orange-500",
  medium: "text-yellow-600", low: "text-green-700",
};
const PRIORITY_LABEL: Record<string, string> = {
  critical: "Kritisk", high: "Høy", medium: "Middels", low: "Lav",
};
const OFFER_STATUS_LABEL: Record<string, string> = {
  pending: "Venter", reviewed: "Gjennomgått", accepted: "Akseptert", rejected: "Avvist",
};

function fmtNok(n?: number) {
  return n ? `kr ${new Intl.NumberFormat("nb-NO").format(n)}` : "–";
}

function fmtRange(r?: { low: number; mid: number; high: number }) {
  if (!r) return "–";
  return `${fmtNok(r.low)} – ${fmtNok(r.high)}`;
}

export default function ForsikringSection({ orgnr }: { orgnr: string }) {
  const { data: needsData, isLoading: needsLoading, mutate: mutateNeeds } = useSWR(
    `needs-${orgnr}`, () => getOrgInsuranceNeeds(orgnr),
  );
  const { data: offers = [], mutate: mutateOffers } = useSWR<InsuranceOffer[]>(
    `offers-${orgnr}`, () => getOrgOffers(orgnr),
  );

  const [needsOpen, setNeedsOpen]       = useState(true);
  const [narrativeOpen, setNarrativeOpen] = useState(false);
  const [offersOpen, setOffersOpen]     = useState(false);

  const [narrative, setNarrative]   = useState<string | null>(null);
  const [riskOffer, setRiskOffer]   = useState<Record<string, unknown> | null>(null);
  const [genLoading, setGenLoading] = useState(false);
  const [genErr, setGenErr]         = useState<string | null>(null);

  async function handleGenerateNarrative() {
    setGenLoading(true); setGenErr(null);
    try {
      const r = await generateNarrative(orgnr);
      setNarrative(r.narrative);
      setNarrativeOpen(true);
    } catch (e) { setGenErr(String(e)); }
    finally { setGenLoading(false); }
  }

  async function handleGenerateOffer() {
    setGenLoading(true); setGenErr(null);
    try {
      const r = await generateRiskOffer(orgnr);
      setRiskOffer(r as Record<string, unknown>);
      setNarrativeOpen(true);
    } catch (e) { setGenErr(String(e)); }
    finally { setGenLoading(false); }
  }

  async function handleDeleteOffer(id: number) {
    await deleteOffer(orgnr, id);
    mutateOffers();
  }

  async function handleStatusChange(id: number, status: string) {
    await updateOfferStatus(orgnr, id, status);
    mutateOffers();
  }

  const needs: InsuranceNeed[] = needsData?.needs ?? [];

  return (
    <div className="space-y-2">
      {/* Insurance needs */}
      <div className="broker-card">
        <button onClick={() => setNeedsOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]">
          <span>🛡️ Forsikringsbehov {needs.length > 0 && `(${needs.length})`}</span>
          {needsOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {needsOpen && (
          <div className="mt-3">
            {needsLoading ? (
              <div className="flex items-center gap-2 text-xs text-[#8A7F74]">
                <Loader2 className="w-4 h-4 animate-spin" /> Estimerer…
              </div>
            ) : needs.length === 0 ? (
              <p className="text-xs text-[#8A7F74]">Ingen behovsdata tilgjengelig.</p>
            ) : (
              <>
                {needsData?.narrative && (
                  <p className="text-xs text-[#8A7F74] mb-3 italic">{needsData.narrative}</p>
                )}
                <div className="divide-y divide-[#EDE8E3]">
                  {needs.map((n, i) => (
                    <div key={i} className="py-2.5">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold text-[#2C3E50]">{n.type}</p>
                        <span className={`text-xs font-medium ${PRIORITY_COLOR[n.priority] ?? "text-[#8A7F74]"}`}>
                          {PRIORITY_LABEL[n.priority] ?? n.priority}
                        </span>
                      </div>
                      <p className="text-xs text-[#8A7F74] mt-0.5">{n.reason}</p>
                      {(n.estimated_coverage_nok || n.estimated_annual_premium_nok) && (
                        <p className="text-xs text-[#8A7F74] mt-0.5">
                          {[
                            n.estimated_coverage_nok && `Dekningssum: ${fmtNok(n.estimated_coverage_nok)}`,
                            n.estimated_annual_premium_nok && `Premie: ${fmtRange(n.estimated_annual_premium_nok)} /år`,
                          ].filter(Boolean).join(" · ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* AI narrative + risk offer */}
      <div className="broker-card">
        <button onClick={() => setNarrativeOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]">
          <span className="flex items-center gap-1.5"><Sparkles className="w-4 h-4" /> AI-risikoanalyse</span>
          {narrativeOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {narrativeOpen && (
          <div className="mt-3 space-y-3">
            <div className="flex gap-2 flex-wrap">
              <button onClick={handleGenerateNarrative} disabled={genLoading}
                className="px-3 py-1.5 text-xs rounded bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1">
                {genLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                Generer risikonarrativ
              </button>
              <button onClick={handleGenerateOffer} disabled={genLoading}
                className="px-3 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1">
                {genLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />}
                Generer forsikringstilbud
              </button>
            </div>
            {genErr && <p className="text-xs text-red-600">{genErr}</p>}

            {narrative && (
              <div className="bg-[#F9F7F4] rounded-lg p-3">
                <p className="text-xs font-semibold text-[#2C3E50] mb-1">Risikonarrativ</p>
                <p className="text-xs text-[#2C3E50] whitespace-pre-wrap">{narrative}</p>
              </div>
            )}

            {riskOffer && (
              <div className="bg-[#F9F7F4] rounded-lg p-3 space-y-2">
                <p className="text-xs font-semibold text-[#2C3E50]">Forsikringstilbud</p>
                {!!riskOffer.sammendrag && (
                  <p className="text-xs text-[#2C3E50] whitespace-pre-wrap">{String(riskOffer.sammendrag)}</p>
                )}
                {!!riskOffer.total_premieanslag && (
                  <p className="text-xs text-[#4A6FA5] font-medium">
                    Totalt premieanslag: {String(riskOffer.total_premieanslag)}
                  </p>
                )}
                {Array.isArray(riskOffer.anbefalinger) && riskOffer.anbefalinger.length > 0 && (
                  <ul className="space-y-1">
                    {(riskOffer.anbefalinger as Record<string, unknown>[]).map((a, i) => (
                      <li key={i} className="text-xs text-[#2C3E50]">
                        • <strong>{String(a.type ?? "")}</strong>{a.begrunnelse ? `: ${String(a.begrunnelse)}` : ""}
                        {!!a.estimert_premie && ` — ${String(a.estimert_premie)}`}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Uploaded offers */}
      <div className="broker-card">
        <button onClick={() => setOffersOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]">
          <span>📎 Innhentede tilbud {offers.length > 0 && `(${offers.length})`}</span>
          {offersOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {offersOpen && (
          <div className="mt-3">
            {offers.length === 0 ? (
              <p className="text-xs text-[#8A7F74]">Ingen tilbud lastet opp.</p>
            ) : (
              <div className="divide-y divide-[#EDE8E3]">
                {offers.map((o) => (
                  <div key={o.id} className="py-2.5 flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-[#2C3E50]">{o.insurer_name}</p>
                      <p className="text-xs text-[#8A7F74] mt-0.5">{o.filename} · {o.uploaded_at.slice(0, 10)}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <select
                        value={o.status ?? "pending"}
                        onChange={(e) => handleStatusChange(o.id, e.target.value)}
                        className="text-xs border border-[#D4C9B8] rounded px-1.5 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
                      >
                        {Object.entries(OFFER_STATUS_LABEL).map(([v, l]) => (
                          <option key={v} value={v}>{l}</option>
                        ))}
                      </select>
                      <button onClick={() => handleDeleteOffer(o.id)} className="text-[#C4BDB4] hover:text-red-500">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
