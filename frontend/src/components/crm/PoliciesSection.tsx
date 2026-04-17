"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getOrgPolicies, createPolicy, deletePolicy, type Policy,
} from "@/lib/api";
import { Trash2, Plus, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { fmtNok } from "@/lib/format";

const PRODUCT_TYPES = [
  "Yrkesskade", "Ansvarsforsikring", "Eiendomsforsikring", "Cyberforsikring",
  "Transportforsikring", "D&O-forsikring", "Nøkkelpersonforsikring",
  "Kredittforsikring", "Reiseforsikring", "Annet",
];

function daysBadge(renewalDate?: string) {
  if (!renewalDate) return null;
  const days = Math.round((new Date(renewalDate).getTime() - Date.now()) / 86400000);
  if (days < 0)  return <span className="text-xs text-red-600">🔴 Utløpt ({Math.abs(days)}d)</span>;
  if (days <= 30) return <span className="text-xs text-orange-600">🟠 {days} dager</span>;
  if (days <= 90) return <span className="text-xs text-yellow-600">🟡 {days} dager</span>;
  return <span className="text-xs text-green-700">🟢 {days} dager</span>;
}


export default function PoliciesSection({ orgnr, onPoliciesLoaded }: {
  orgnr: string;
  onPoliciesLoaded?: (policies: Policy[]) => void;
}) {
  const { data: policies = [], mutate } = useSWR<Policy[]>(
    `policies-${orgnr}`,
    async () => {
      const data = await getOrgPolicies(orgnr);
      onPoliciesLoaded?.(data);
      return data;
    },
  );
  const [listOpen, setListOpen] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving]     = useState(false);
  const [err, setErr]           = useState<string | null>(null);

  const [insurer, setInsurer]               = useState("");
  const [productType, setProductType]       = useState(PRODUCT_TYPES[0]);
  const [policyNumber, setPolicyNumber]     = useState("");
  const [status, setStatus]                 = useState("active");
  const [premium, setPremium]               = useState("");
  const [coverage, setCoverage]             = useState("");
  const [startDate, setStartDate]           = useState("");
  const [renewalDate, setRenewalDate]       = useState("");
  const [docUrl, setDocUrl]                 = useState("");
  const [notes, setNotes]                   = useState("");
  const [commissionRate, setCommissionRate] = useState("");
  const [commissionAmt, setCommissionAmt]   = useState("");

  async function handleDelete(id: number) {
    await deletePolicy(orgnr, id);
    mutate();
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!insurer.trim()) return;
    setSaving(true); setErr(null);
    try {
      await createPolicy(orgnr, {
        insurer, product_type: productType, policy_number: policyNumber || undefined,
        status, insurance_type: productType,
        annual_premium_nok: premium ? Number(premium) : undefined,
        coverage_amount_nok: coverage ? Number(coverage) : undefined,
        start_date: startDate || undefined, renewal_date: renewalDate || undefined,
        document_url: docUrl || undefined, notes: notes || undefined,
        commission_rate_pct: commissionRate ? Number(commissionRate) : undefined,
        commission_amount_nok: commissionAmt ? Number(commissionAmt) : undefined,
      });
      setInsurer(""); setPolicyNumber(""); setPremium(""); setCoverage("");
      setStartDate(""); setRenewalDate(""); setDocUrl(""); setNotes("");
      setCommissionRate(""); setCommissionAmt(""); setFormOpen(false);
      mutate();
    } catch (e) { setErr(String(e)); }
    finally { setSaving(false); }
  }

  return (
    <div className="space-y-2">
      {/* List */}
      <div className="broker-card">
        <button onClick={() => setListOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]">
          <span>📋 Forsikringsavtaler {policies.length > 0 && `(${policies.length})`}</span>
          {listOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {listOpen && (
          <div className="mt-3">
            {policies.length === 0 ? (
              <p className="text-xs text-[#8A7F74]">Ingen forsikringsavtaler registrert.</p>
            ) : (
              <div className="divide-y divide-[#EDE8E3]">
                {policies.map((p) => (
                  <div key={p.id} className="py-2.5 flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-[#2C3E50]">
                        {p.insurer} — {p.product_type}
                      </p>
                      <p className="text-xs text-[#8A7F74] mt-0.5">
                        {[
                          p.policy_number && `Avtalenr: ${p.policy_number}`,
                          p.annual_premium_nok && `Premie: ${fmtNok(p.annual_premium_nok)}`,
                          p.commission_rate_pct != null && `Provisjon: ${p.commission_rate_pct}%`,
                        ].filter(Boolean).join(" · ")}
                      </p>
                      {p.document_url && (
                        <a href={p.document_url} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-[#4A6FA5] hover:underline mt-0.5">
                          📄 Avtaledokument <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                      {p.notes && (
                        <p className="text-xs text-[#8A7F74] italic mt-1 whitespace-pre-wrap">
                          {p.notes}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {daysBadge(p.renewal_date)}
                      <button onClick={() => handleDelete(p.id)} className="text-[#C4BDB4] hover:text-red-500">
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

      {/* Add form */}
      <div className="broker-card">
        <button onClick={() => setFormOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]">
          <span className="flex items-center gap-1.5"><Plus className="w-4 h-4" /> Registrer forsikringsavtale</span>
          {formOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {formOpen && (
          <form onSubmit={handleAdd} className="mt-3 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label-xs" htmlFor="policy-insurer">Forsikringsselskap *</label>
                <input id="policy-insurer" value={insurer} onChange={(e) => setInsurer(e.target.value)} required
                  className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs" htmlFor="policy-product-type">Produkttype *</label>
                <select id="policy-product-type" value={productType} onChange={(e) => setProductType(e.target.value)} className="input-sm w-full">
                  {PRODUCT_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="label-xs" htmlFor="policy-number">Avtalenummer</label>
                <input id="policy-number" value={policyNumber} onChange={(e) => setPolicyNumber(e.target.value)} className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs" htmlFor="policy-status">Status</label>
                <select id="policy-status" value={status} onChange={(e) => setStatus(e.target.value)} className="input-sm w-full">
                  {["active","pending","expired","cancelled"].map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="label-xs" htmlFor="policy-premium">Årspremie (kr)</label>
                <input id="policy-premium" type="number" value={premium} onChange={(e) => setPremium(e.target.value)} min="0" step="1000" className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs" htmlFor="policy-coverage">Forsikringssum (kr)</label>
                <input id="policy-coverage" type="number" value={coverage} onChange={(e) => setCoverage(e.target.value)} min="0" step="100000" className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs" htmlFor="policy-start-date">Startdato</label>
                <input id="policy-start-date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs" htmlFor="policy-renewal-date">Fornyelsesdato</label>
                <input id="policy-renewal-date" type="date" value={renewalDate} onChange={(e) => setRenewalDate(e.target.value)} className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs" htmlFor="policy-commission-rate">Provisjonssats (%)</label>
                <input id="policy-commission-rate" type="number" value={commissionRate} onChange={(e) => setCommissionRate(e.target.value)}
                  min="0" max="100" step="0.1" placeholder="f.eks. 12.5" className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs" htmlFor="policy-commission-amount">Provisjonsbeløp (kr)</label>
                <input id="policy-commission-amount" type="number" value={commissionAmt} onChange={(e) => setCommissionAmt(e.target.value)}
                  min="0" step="100" placeholder="Beregnes automatisk om tomt" className="input-sm w-full" />
              </div>
            </div>
            <div>
              <label className="label-xs" htmlFor="policy-doc-url">Dokument-URL</label>
              <input id="policy-doc-url" type="url" value={docUrl} onChange={(e) => setDocUrl(e.target.value)} placeholder="https://..." className="input-sm w-full" />
            </div>
            <div>
              <label className="label-xs" htmlFor="policy-notes">Notater</label>
              <textarea id="policy-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
                className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5]" />
            </div>
            {err && <p className="text-xs text-red-600">{err}</p>}
            <div className="flex gap-2">
              <button type="submit" disabled={saving}
                className="px-4 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50">
                {saving ? "Lagrer…" : "Lagre avtale"}
              </button>
              <button type="button" onClick={() => setFormOpen(false)}
                className="px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#8A7F74]">
                Avbryt
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
