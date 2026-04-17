"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getOrgClaims, createClaim, deleteClaim, type Claim, type Policy,
} from "@/lib/api";
import { Trash2, Plus, ChevronDown, ChevronUp } from "lucide-react";
import { fmtNok } from "@/lib/format";

const STATUS_ICON: Record<string, string> = {
  open: "🔵", in_review: "🟡", settled: "🟢", rejected: "🔴",
};
const STATUS_LABEL: Record<string, string> = {
  open: "Åpen", in_review: "Under behandling", settled: "Avgjort", rejected: "Avvist",
};


export default function ClaimsSection({ orgnr, policies }: {
  orgnr: string;
  policies: Policy[];
}) {
  const { data: claims = [], mutate } = useSWR<Claim[]>(
    `claims-${orgnr}`, () => getOrgClaims(orgnr),
  );
  const [listOpen, setListOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving]     = useState(false);
  const [err, setErr]           = useState<string | null>(null);

  const [policyId, setPolicyId]     = useState<string>("");
  const [claimNumber, setClaimNumber] = useState("");
  const [status, setStatus]         = useState("open");
  const [incidentDate, setIncidentDate] = useState("");
  const [reportedDate, setReportedDate] = useState("");
  const [estimated, setEstimated]   = useState("");
  const [insContact, setInsContact] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes]           = useState("");

  async function handleDelete(id: number) {
    await deleteClaim(orgnr, id);
    mutate();
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setErr(null);
    try {
      await createClaim(orgnr, {
        policy_id: policyId ? Number(policyId) : undefined,
        claim_number: claimNumber || undefined, status,
        incident_date: incidentDate || undefined,
        reported_date: reportedDate || undefined,
        estimated_amount_nok: estimated ? Number(estimated) : undefined,
        insurer_contact: insContact || undefined,
        description: description || undefined,
        notes: notes || undefined,
      });
      setClaimNumber(""); setIncidentDate(""); setReportedDate(""); setEstimated("");
      setInsContact(""); setDescription(""); setNotes(""); setFormOpen(false);
      mutate();
    } catch (e) { setErr(String(e)); }
    finally { setSaving(false); }
  }

  return (
    <div className="space-y-2">
      <div className="broker-card">
        <button onClick={() => setListOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]">
          <span>🔥 Skader og krav {claims.length > 0 && `(${claims.length})`}</span>
          {listOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {listOpen && (
          <div className="mt-3">
            {claims.length === 0 ? (
              <p className="text-xs text-[#8A7F74]">Ingen registrerte skader.</p>
            ) : (
              <div className="divide-y divide-[#EDE8E3]">
                {claims.map((c) => (
                  <div key={c.id} className="py-2.5 flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-[#2C3E50]">
                        {c.claim_number || `Skade #${c.id}`}
                      </p>
                      <p className="text-xs text-[#8A7F74]">
                        {[
                          c.incident_date && `Hendelse: ${c.incident_date}`,
                          c.estimated_amount_nok && `Estimert: ${fmtNok(c.estimated_amount_nok)}`,
                          c.settled_amount_nok && `Oppgjort: ${fmtNok(c.settled_amount_nok)}`,
                        ].filter(Boolean).join(" · ")}
                      </p>
                      {c.description && (
                        <p className="text-xs text-[#8A7F74] mt-1 line-clamp-2">{c.description}</p>
                      )}
                      {c.notes && (
                        <p className="text-xs text-[#8A7F74] italic mt-1 whitespace-pre-wrap">{c.notes}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-xs">
                        {STATUS_ICON[c.status] ?? "⚪"} {STATUS_LABEL[c.status] ?? c.status}
                      </span>
                      <button onClick={() => handleDelete(c.id)} className="text-[#C4BDB4] hover:text-red-500">
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

      <div className="broker-card">
        <button onClick={() => setFormOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]">
          <span className="flex items-center gap-1.5"><Plus className="w-4 h-4" /> Registrer skade</span>
          {formOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {formOpen && (
          <form onSubmit={handleAdd} className="mt-3 space-y-3">
            {policies.length === 0 ? (
              <p className="text-xs text-[#8A7F74]">
                Ingen forsikringsavtaler å knytte skaden til. Registrer en avtale først.
              </p>
            ) : (
              <>
                <div>
                  <label className="label-xs" htmlFor="claim-policy">Forsikringsavtale *</label>
                  <select id="claim-policy" value={policyId} onChange={(e) => setPolicyId(e.target.value)} className="input-sm w-full" required>
                    <option value="">Velg avtale…</option>
                    {policies.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.insurer} — {p.product_type} ({p.policy_number || "uten nr"})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label-xs" htmlFor="claim-number">Skadenummer</label>
                    <input id="claim-number" value={claimNumber} onChange={(e) => setClaimNumber(e.target.value)} className="input-sm w-full" />
                  </div>
                  <div>
                    <label className="label-xs" htmlFor="claim-status">Status</label>
                    <select id="claim-status" value={status} onChange={(e) => setStatus(e.target.value)} className="input-sm w-full">
                      {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="label-xs" htmlFor="claim-incident-date">Hendelsesdato</label>
                    <input id="claim-incident-date" type="date" value={incidentDate} onChange={(e) => setIncidentDate(e.target.value)} className="input-sm w-full" />
                  </div>
                  <div>
                    <label className="label-xs" htmlFor="claim-reported-date">Meldt dato</label>
                    <input id="claim-reported-date" type="date" value={reportedDate} onChange={(e) => setReportedDate(e.target.value)} className="input-sm w-full" />
                  </div>
                  <div>
                    <label className="label-xs" htmlFor="claim-estimated-amount">Estimert beløp (kr)</label>
                    <input id="claim-estimated-amount" type="number" value={estimated} onChange={(e) => setEstimated(e.target.value)} min="0" step="10000" className="input-sm w-full" />
                  </div>
                  <div>
                    <label className="label-xs" htmlFor="claim-insurer-contact">Kontakt hos forsikringsselskap</label>
                    <input id="claim-insurer-contact" value={insContact} onChange={(e) => setInsContact(e.target.value)} className="input-sm w-full" />
                  </div>
                </div>
                <div>
                  <label className="label-xs" htmlFor="claim-description">Beskrivelse</label>
                  <textarea id="claim-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
                    className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]" />
                </div>
                <div>
                  <label className="label-xs" htmlFor="claim-notes">Notater</label>
                  <textarea id="claim-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
                    placeholder="Interne notater (synlig kun for megler)"
                    className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]" />
                </div>
                {err && <p className="text-xs text-red-600">{err}</p>}
                <div className="flex gap-2">
                  <button type="submit" disabled={saving}
                    className="px-4 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50">
                    {saving ? "Registrerer…" : "Registrer skade"}
                  </button>
                  <button type="button" onClick={() => setFormOpen(false)}
                    className="px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#8A7F74]">Avbryt</button>
                </div>
              </>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
