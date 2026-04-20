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
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useT } from "@/lib/i18n";

const STATUS_COLORS: Record<string, string> = {
  pending:   "bg-amber-100 text-amber-700",
  quoted:    "bg-blue-100 text-blue-700",
  declined:  "bg-red-100 text-red-700",
  withdrawn: "bg-gray-100 text-gray-600",
};

// Product types are enum values sent to backend — keep Norwegian canon
const PRODUCT_TYPES = [
  "Motorvognforsikring", "Næringseiendom", "Ansvarsforsikring",
  "Yrkesskadeforsikring", "Reiseforsikring", "Personforsikring",
  "Cyberforsikring", "Styreansvarsforsikring", "Varetransportforsikring",
  "Avbruddsforsikring",
];

export default function SubmissionsSection({ orgnr }: { orgnr: string }) {
  const T = useT();
  const STATUS_LABELS: Record<string, string> = {
    pending:   T("Avventer"),
    quoted:    T("Tilbud mottatt"),
    declined:  T("Avslått"),
    withdrawn: T("Trukket"),
  };
  const { data: submissions = [], mutate } = useSWR<Submission[]>(
    `submissions-${orgnr}`,
    () => getOrgSubmissions(orgnr),
  );
  const { data: insurers = [] } = useSWR<Insurer[]>("/insurers", getInsurers);

  const [open, setOpen]       = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving]   = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

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

  function handleDelete(id: number) {
    setDeleteId(id);
  }

  async function performDelete(id: number) {
    await deleteSubmission(id);
    mutate();
  }

  return (
    <div className="broker-card">
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 text-sm font-semibold text-foreground"
        >
          <Send className="w-4 h-4 text-primary" />
          {T("Markedsplassering")}
          <span className="text-xs text-muted-foreground font-normal">
            ({submissions.length})
          </span>
          {open ? <ChevronUp className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />}
        </button>
        <button
          onClick={() => setFormOpen((v) => !v)}
          className="flex items-center gap-1 text-xs text-primary hover:text-primary/80"
        >
          <Plus className="w-3.5 h-3.5" />
          {T("Legg til")}
        </button>
      </div>

      {open && (
        <div className="space-y-3">
          {formOpen && (
            <form onSubmit={handleCreate} className="border border-border rounded-lg p-3 space-y-3 bg-background">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground font-medium" htmlFor="submission-insurer">{T("Forsikringsselskap")} *</label>
                  <select
                    id="submission-insurer"
                    value={insurerId}
                    onChange={(e) => setInsurerId(e.target.value ? Number(e.target.value) : "")}
                    required
                    className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="">{T("Velg selskap…")}</option>
                    {insurers.map((ins) => (
                      <option key={ins.id} value={ins.id}>{ins.name}</option>
                    ))}
                  </select>
                  {insurers.length === 0 && (
                    <p className="text-xs text-amber-600 mt-1">
                      {T("Ingen selskaper.")} <a href="/insurers" className="underline">{T("Legg til")}</a>.
                    </p>
                  )}
                </div>
                <div>
                  <label className="text-xs text-muted-foreground font-medium" htmlFor="submission-product">{T("Produkt")} *</label>
                  <select
                    id="submission-product"
                    value={productType}
                    onChange={(e) => setProductType(e.target.value)}
                    className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    {PRODUCT_TYPES.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground font-medium" htmlFor="submission-requested-at">{T("Sendt dato")}</label>
                  <input
                    id="submission-requested-at"
                    type="date"
                    value={requestedAt}
                    onChange={(e) => setRequestedAt(e.target.value)}
                    className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground font-medium" htmlFor="submission-notes">{T("Notater")}</label>
                  <input
                    id="submission-notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    placeholder={T("Valgfritt")}
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setFormOpen(false)}
                  className="text-xs text-muted-foreground hover:text-foreground px-3 py-1.5 border border-gray-200 rounded-md">
                  {T("Avbryt")}
                </button>
                <button type="submit" disabled={saving || !insurerId}
                  className="text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded-md hover:bg-primary/90 disabled:opacity-50">
                  {saving ? T("Lagrer…") : T("Legg til")}
                </button>
              </div>
            </form>
          )}

          {submissions.length === 0 && !formOpen && (
            <p className="text-xs text-muted-foreground text-center py-4">
              {T("Ingen markedsforespørsler ennå")}
            </p>
          )}

          {submissions.map((sub) => (
            <div key={sub.id} className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-foreground">
                    {sub.insurer_name ?? `${T("Selskap")} #${sub.insurer_id}`}
                  </span>
                  <span className="text-xs text-muted-foreground">{sub.product_type}</span>
                  {sub.requested_at && (
                    <span className="text-xs text-muted-foreground">
                      · {new Date(sub.requested_at).toLocaleDateString("nb-NO")}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <select
                    value={sub.status}
                    onChange={(e) => handleStatusChange(sub, e.target.value as Submission["status"])}
                    className={`text-xs px-2 py-0.5 rounded-full border-0 font-medium cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-ring ${STATUS_COLORS[sub.status]}`}
                  >
                    {Object.entries(STATUS_LABELS).map(([val, label]) => (
                      <option key={val} value={val}>{label}</option>
                    ))}
                  </select>
                  {sub.premium_offered_nok != null && (
                    <span className="text-xs text-foreground font-medium">
                      {fmtNok(sub.premium_offered_nok)}
                    </span>
                  )}
                  {sub.notes && (
                    <span className="text-xs text-muted-foreground truncate max-w-xs">{sub.notes}</span>
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

      <ConfirmDialog
        open={deleteId !== null}
        onOpenChange={(o) => { if (!o) setDeleteId(null); }}
        title={T("Slett forespørsel?")}
        description={T("Handlingen kan ikke angres.")}
        confirmLabel={T("Slett")}
        destructive
        onConfirm={() => {
          if (deleteId !== null) performDelete(deleteId);
        }}
      />
    </div>
  );
}
