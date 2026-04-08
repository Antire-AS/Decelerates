"use client";

import { useState } from "react";
import useSWR from "swr";
import { Plus, Trash2, ChevronDown, ChevronUp, Send } from "lucide-react";
import {
  getOrgSubmissions, createSubmission, updateSubmission, deleteSubmission,
  getInsurers,
  type Submission, type Insurer,
} from "@/lib/api";
import { fmtNok } from "@/lib/format";

const STATUS_LABELS: Record<string, string> = {
  pending:   "Avventer",
  quoted:    "Tilbud mottatt",
  declined:  "Avslått",
  withdrawn: "Trukket",
};

const STATUS_COLORS: Record<string, string> = {
  pending:   "bg-amber-100 text-amber-700",
  quoted:    "bg-blue-100 text-blue-700",
  declined:  "bg-red-100 text-red-700",
  withdrawn: "bg-gray-100 text-gray-600",
};

const PRODUCT_TYPES = [
  "Motorvognforsikring", "Næringseiendom", "Ansvarsforsikring",
  "Yrkesskadeforsikring", "Reiseforsikring", "Personforsikring",
  "Cyberforsikring", "Styreansvarsforsikring", "Varetransportforsikring",
  "Avbruddsforsikring",
];

export default function SubmissionsSection({ orgnr }: { orgnr: string }) {
  const { data: submissions = [], mutate } = useSWR<Submission[]>(
    `submissions-${orgnr}`,
    () => getOrgSubmissions(orgnr),
  );
  const { data: insurers = [] } = useSWR<Insurer[]>("/insurers", getInsurers);

  const [open, setOpen]       = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving]   = useState(false);

  // Form state
  const [insurerId, setInsurerId]     = useState<number | "">("");
  const [productType, setProductType] = useState(PRODUCT_TYPES[0]);
  const [requestedAt, setRequestedAt] = useState("");
  const [notes, setNotes]             = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!insurerId) return;
    setSaving(true);
    try {
      await createSubmission(orgnr, {
        insurer_id: Number(insurerId),
        product_type: productType,
        requested_at: requestedAt || undefined,
        status: "pending",
        notes: notes.trim() || undefined,
      });
      setInsurerId(""); setProductType(PRODUCT_TYPES[0]);
      setRequestedAt(""); setNotes("");
      setFormOpen(false);
      mutate();
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(sub: Submission, status: Submission["status"]) {
    await updateSubmission(sub.id, { status });
    mutate();
  }

  async function handleDelete(id: number) {
    if (!confirm("Slett forespørsel?")) return;
    await deleteSubmission(id);
    mutate();
  }

  return (
    <div className="broker-card">
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 text-sm font-semibold text-[#2C3E50]"
        >
          <Send className="w-4 h-4 text-[#4A6FA5]" />
          Markedsplassering
          <span className="text-xs text-[#8A7F74] font-normal">
            ({submissions.length})
          </span>
          {open ? <ChevronUp className="w-3 h-3 text-[#8A7F74]" /> : <ChevronDown className="w-3 h-3 text-[#8A7F74]" />}
        </button>
        <button
          onClick={() => setFormOpen((v) => !v)}
          className="flex items-center gap-1 text-xs text-[#4A6FA5] hover:text-[#3a5f95]"
        >
          <Plus className="w-3.5 h-3.5" />
          Legg til
        </button>
      </div>

      {open && (
        <div className="space-y-3">
          {formOpen && (
            <form onSubmit={handleCreate} className="border border-[#C5D0E8] rounded-lg p-3 space-y-3 bg-[#F8F9FB]">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-[#8A7F74] font-medium">Forsikringsselskap *</label>
                  <select
                    value={insurerId}
                    onChange={(e) => setInsurerId(e.target.value ? Number(e.target.value) : "")}
                    required
                    className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
                  >
                    <option value="">Velg selskap…</option>
                    {insurers.map((ins) => (
                      <option key={ins.id} value={ins.id}>{ins.name}</option>
                    ))}
                  </select>
                  {insurers.length === 0 && (
                    <p className="text-xs text-amber-600 mt-1">
                      Ingen selskaper. <a href="/insurers" className="underline">Legg til</a>.
                    </p>
                  )}
                </div>
                <div>
                  <label className="text-xs text-[#8A7F74] font-medium">Produkt *</label>
                  <select
                    value={productType}
                    onChange={(e) => setProductType(e.target.value)}
                    className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
                  >
                    {PRODUCT_TYPES.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-[#8A7F74] font-medium">Sendt dato</label>
                  <input
                    type="date"
                    value={requestedAt}
                    onChange={(e) => setRequestedAt(e.target.value)}
                    className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
                  />
                </div>
                <div>
                  <label className="text-xs text-[#8A7F74] font-medium">Notater</label>
                  <input
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
                    placeholder="Valgfritt"
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setFormOpen(false)}
                  className="text-xs text-[#8A7F74] hover:text-[#2C3E50] px-3 py-1.5 border border-gray-200 rounded-md">
                  Avbryt
                </button>
                <button type="submit" disabled={saving || !insurerId}
                  className="text-xs bg-[#4A6FA5] text-white px-3 py-1.5 rounded-md hover:bg-[#3a5f95] disabled:opacity-50">
                  {saving ? "Lagrer…" : "Legg til"}
                </button>
              </div>
            </form>
          )}

          {submissions.length === 0 && !formOpen && (
            <p className="text-xs text-[#8A7F74] text-center py-4">
              Ingen markedsforespørsler ennå
            </p>
          )}

          {submissions.map((sub) => (
            <div key={sub.id} className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-[#2C3E50]">
                    {sub.insurer_name ?? `Selskap #${sub.insurer_id}`}
                  </span>
                  <span className="text-xs text-[#8A7F74]">{sub.product_type}</span>
                  {sub.requested_at && (
                    <span className="text-xs text-[#8A7F74]">
                      · {new Date(sub.requested_at).toLocaleDateString("nb-NO")}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <select
                    value={sub.status}
                    onChange={(e) => handleStatusChange(sub, e.target.value as Submission["status"])}
                    className={`text-xs px-2 py-0.5 rounded-full border-0 font-medium cursor-pointer focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] ${STATUS_COLORS[sub.status]}`}
                  >
                    {Object.entries(STATUS_LABELS).map(([val, label]) => (
                      <option key={val} value={val}>{label}</option>
                    ))}
                  </select>
                  {sub.premium_offered_nok != null && (
                    <span className="text-xs text-[#2C3E50] font-medium">
                      {fmtNok(sub.premium_offered_nok)}
                    </span>
                  )}
                  {sub.notes && (
                    <span className="text-xs text-[#8A7F74] truncate max-w-xs">{sub.notes}</span>
                  )}
                </div>
              </div>
              <button onClick={() => handleDelete(sub.id)} className="text-red-300 hover:text-red-500 flex-shrink-0">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
