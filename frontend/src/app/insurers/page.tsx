"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  Building2, Plus, Trash2, ChevronDown, ChevronUp, Pencil, X,
} from "lucide-react";
import {
  getInsurers, createInsurer, updateInsurer, deleteInsurer,
  type Insurer,
} from "@/lib/api";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useT } from "@/lib/i18n";

const PRODUCT_TYPES = [
  "Motorvognforsikring",
  "Næringseiendom",
  "Ansvarsforsikring",
  "Yrkesskadeforsikring",
  "Reiseforsikring",
  "Personforsikring",
  "Cyberforsikring",
  "Styreansvarsforsikring",
  "Varetransportforsikring",
  "Avbruddsforsikring",
];

// ── Insurer form ──────────────────────────────────────────────────────────────

function InsurerForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Partial<Insurer>;
  onSave: (data: Omit<Insurer, "id" | "firm_id" | "created_at">) => Promise<void>;
  onCancel: () => void;
}) {
  const T = useT();
  const [name, setName] = useState(initial?.name ?? "");
  const [orgNumber, setOrgNumber] = useState(initial?.org_number ?? "");
  const [contactName, setContactName] = useState(initial?.contact_name ?? "");
  const [contactEmail, setContactEmail] = useState(initial?.contact_email ?? "");
  const [contactPhone, setContactPhone] = useState(initial?.contact_phone ?? "");
  const [appetite, setAppetite] = useState<string[]>(initial?.appetite ?? []);
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [saving, setSaving] = useState(false);

  function toggleAppetite(p: string) {
    setAppetite((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave({
        name: name.trim(),
        org_number: orgNumber.trim() || undefined,
        contact_name: contactName.trim() || undefined,
        contact_email: contactEmail.trim() || undefined,
        contact_phone: contactPhone.trim() || undefined,
        appetite: appetite.length ? appetite : undefined,
        notes: notes.trim() || undefined,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="insurer-name">{T("Navn")} *</label>
          <input
            id="insurer-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full mt-1 px-3 py-1.5 text-sm border border-brand-stone rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            placeholder={T("f.eks. If Skadeforsikring")}
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="insurer-orgnr">{T("Org.nr")}</label>
          <input
            id="insurer-orgnr"
            value={orgNumber}
            onChange={(e) => setOrgNumber(e.target.value)}
            className="w-full mt-1 px-3 py-1.5 text-sm border border-brand-stone rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            placeholder={T("9 siffer")}
            maxLength={9}
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="insurer-contact-name">{T("Kontaktperson")}</label>
          <input
            id="insurer-contact-name"
            value={contactName}
            onChange={(e) => setContactName(e.target.value)}
            className="w-full mt-1 px-3 py-1.5 text-sm border border-brand-stone rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="insurer-contact-email">{T("E-post")}</label>
          <input
            id="insurer-contact-email"
            type="email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
            className="w-full mt-1 px-3 py-1.5 text-sm border border-brand-stone rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="insurer-contact-phone">{T("Telefon")}</label>
          <input
            id="insurer-contact-phone"
            value={contactPhone}
            onChange={(e) => setContactPhone(e.target.value)}
            className="w-full mt-1 px-3 py-1.5 text-sm border border-brand-stone rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
        </div>
      </div>

      <div>
        <p className="text-xs text-muted-foreground font-medium">{T("Produktappetitt")}</p>
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          {PRODUCT_TYPES.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => toggleAppetite(p)}
              className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                appetite.includes(p)
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-card text-muted-foreground border-brand-stone hover:border-primary"
              }`}
            >
              {T(p)}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-muted-foreground font-medium" htmlFor="insurer-notes">{T("Notater")}</label>
        <textarea
          id="insurer-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full mt-1 px-3 py-1.5 text-sm border border-brand-stone rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
        />
      </div>

      <div className="flex gap-2 justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground border border-brand-stone rounded-md"
        >
          {T("Avbryt")}
        </button>
        <button
          type="submit"
          disabled={saving || !name.trim()}
          className="px-4 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? T("Lagrer…") : T("Lagre")}
        </button>
      </div>
    </form>
  );
}

// ── Insurer card ──────────────────────────────────────────────────────────────

function InsurerCard({
  insurer,
  onDeleted,
  onUpdated,
}: {
  insurer: Insurer;
  onDeleted: () => void;
  onUpdated: (updated: Insurer) => void;
}) {
  const T = useT();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  function handleDelete() {
    setConfirmDelete(true);
  }

  async function performDelete() {
    await deleteInsurer(insurer.id);
    onDeleted();
  }

  async function handleUpdate(data: Omit<Insurer, "id" | "firm_id" | "created_at">) {
    const updated = await updateInsurer(insurer.id, data);
    onUpdated(updated);
    setEditing(false);
  }

  return (
    <div className="broker-card">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center flex-shrink-0">
            <Building2 className="w-4 h-4 text-primary" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{insurer.name}</p>
            {insurer.org_number && (
              <p className="text-xs text-muted-foreground">{T("Org.nr")} {insurer.org_number}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setOpen((v) => !v); setEditing(false); }}
            className="text-xs text-primary hover:underline flex items-center gap-1"
          >
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {open ? T("Skjul") : T("Vis")}
          </button>
          <button onClick={() => { setOpen(true); setEditing(true); }} className="text-muted-foreground hover:text-primary">
            <Pencil className="w-4 h-4" />
          </button>
          <button onClick={handleDelete} className="text-red-400 hover:text-red-600">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {open && (
        <div className="mt-4">
          {editing ? (
            <InsurerForm
              initial={insurer}
              onSave={handleUpdate}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <div className="space-y-3 text-sm">
              {(insurer.contact_name || insurer.contact_email || insurer.contact_phone) && (
                <div>
                  <p className="text-xs text-muted-foreground font-medium mb-1">{T("Kontakt")}</p>
                  <p className="text-foreground">{insurer.contact_name || "–"}</p>
                  {insurer.contact_email && (
                    <a href={`mailto:${insurer.contact_email}`} className="text-xs text-primary hover:underline">
                      {insurer.contact_email}
                    </a>
                  )}
                  {insurer.contact_phone && (
                    <p className="text-xs text-muted-foreground">{insurer.contact_phone}</p>
                  )}
                </div>
              )}
              {insurer.appetite && insurer.appetite.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground font-medium mb-1.5">{T("Produktappetitt")}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {insurer.appetite.map((p) => (
                      <span key={p} className="px-2 py-0.5 text-xs rounded-full bg-accent text-primary">
                        {T(p)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {insurer.notes && (
                <div>
                  <p className="text-xs text-muted-foreground font-medium mb-1">{T("Notater")}</p>
                  <p className="text-foreground text-xs">{insurer.notes}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`${T("Slett")} ${insurer.name}?`}
        description={T("Handlingen kan ikke angres.")}
        confirmLabel={T("Slett")}
        destructive
        onConfirm={performDelete}
      />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function InsurersPage() {
  const T = useT();
  const { data: insurers, isLoading, mutate: refresh } = useSWR<Insurer[]>(
    "/insurers",
    getInsurers,
  );
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");

  async function handleCreate(data: Omit<Insurer, "id" | "firm_id" | "created_at">) {
    await createInsurer(data);
    setShowForm(false);
    refresh();
  }

  const filtered = (insurers ?? []).filter((ins) =>
    ins.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{T("Forsikringsselskaper")}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {T("Administrer forsikringsselskaper og deres produktappetitt")}
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-md hover:bg-primary/90"
        >
          {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          {showForm ? T("Avbryt") : T("Legg til")}
        </button>
      </div>

      {showForm && (
        <div className="broker-card">
          <p className="text-sm font-semibold text-foreground mb-4">{T("Nytt forsikringsselskap")}</p>
          <InsurerForm onSave={handleCreate} onCancel={() => setShowForm(false)} />
        </div>
      )}

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder={T("Søk etter selskap…")}
        className="w-full px-3 py-2 text-sm border border-brand-stone rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />

      {isLoading && (
        <p className="text-sm text-muted-foreground text-center py-8">{T("Laster…")}</p>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <Building2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">
            {search ? T("Ingen treff") : T("Ingen forsikringsselskaper lagt til ennå")}
          </p>
        </div>
      )}

      <div className="space-y-3">
        {filtered.map((ins) => (
          <InsurerCard
            key={ins.id}
            insurer={ins}
            onDeleted={refresh}
            onUpdated={() => refresh()}
          />
        ))}
      </div>

      {!isLoading && filtered.length > 0 && (
        <p className="text-xs text-muted-foreground text-center">
          {filtered.length} {filtered.length !== 1 ? T("selskaper") : T("selskap")}
        </p>
      )}
    </div>
  );
}
