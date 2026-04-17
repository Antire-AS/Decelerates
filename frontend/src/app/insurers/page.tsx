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
          <label className="text-xs text-[#8A7F74] font-medium" htmlFor="insurer-name">Navn *</label>
          <input
            id="insurer-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
            placeholder="f.eks. If Skadeforsikring"
          />
        </div>
        <div>
          <label className="text-xs text-[#8A7F74] font-medium" htmlFor="insurer-orgnr">Org.nr</label>
          <input
            id="insurer-orgnr"
            value={orgNumber}
            onChange={(e) => setOrgNumber(e.target.value)}
            className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
            placeholder="9 siffer"
            maxLength={9}
          />
        </div>
        <div>
          <label className="text-xs text-[#8A7F74] font-medium" htmlFor="insurer-contact-name">Kontaktperson</label>
          <input
            id="insurer-contact-name"
            value={contactName}
            onChange={(e) => setContactName(e.target.value)}
            className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
          />
        </div>
        <div>
          <label className="text-xs text-[#8A7F74] font-medium" htmlFor="insurer-contact-email">E-post</label>
          <input
            id="insurer-contact-email"
            type="email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
            className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
          />
        </div>
        <div>
          <label className="text-xs text-[#8A7F74] font-medium" htmlFor="insurer-contact-phone">Telefon</label>
          <input
            id="insurer-contact-phone"
            value={contactPhone}
            onChange={(e) => setContactPhone(e.target.value)}
            className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
          />
        </div>
      </div>

      <div>
        <p className="text-xs text-[#8A7F74] font-medium">Produktappetitt</p>
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          {PRODUCT_TYPES.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => toggleAppetite(p)}
              className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                appetite.includes(p)
                  ? "bg-[#4A6FA5] text-white border-[#4A6FA5]"
                  : "bg-white text-[#8A7F74] border-gray-200 hover:border-[#4A6FA5]"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-[#8A7F74] font-medium" htmlFor="insurer-notes">Notater</label>
        <textarea
          id="insurer-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] resize-none"
        />
      </div>

      <div className="flex gap-2 justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-sm text-[#8A7F74] hover:text-[#2C3E50] border border-gray-200 rounded-md"
        >
          Avbryt
        </button>
        <button
          type="submit"
          disabled={saving || !name.trim()}
          className="px-4 py-1.5 text-sm bg-[#4A6FA5] text-white rounded-md hover:bg-[#3a5f95] disabled:opacity-50"
        >
          {saving ? "Lagrer…" : "Lagre"}
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
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);

  async function handleDelete() {
    if (!confirm(`Slett ${insurer.name}?`)) return;
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
          <div className="w-8 h-8 rounded-full bg-[#E8EDF5] flex items-center justify-center flex-shrink-0">
            <Building2 className="w-4 h-4 text-[#4A6FA5]" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[#2C3E50]">{insurer.name}</p>
            {insurer.org_number && (
              <p className="text-xs text-[#8A7F74]">Org.nr {insurer.org_number}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setOpen((v) => !v); setEditing(false); }}
            className="text-xs text-[#4A6FA5] hover:underline flex items-center gap-1"
          >
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {open ? "Skjul" : "Vis"}
          </button>
          <button onClick={() => { setOpen(true); setEditing(true); }} className="text-[#8A7F74] hover:text-[#4A6FA5]">
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
                  <p className="text-xs text-[#8A7F74] font-medium mb-1">Kontakt</p>
                  <p className="text-[#2C3E50]">{insurer.contact_name || "–"}</p>
                  {insurer.contact_email && (
                    <a href={`mailto:${insurer.contact_email}`} className="text-xs text-[#4A6FA5] hover:underline">
                      {insurer.contact_email}
                    </a>
                  )}
                  {insurer.contact_phone && (
                    <p className="text-xs text-[#8A7F74]">{insurer.contact_phone}</p>
                  )}
                </div>
              )}
              {insurer.appetite && insurer.appetite.length > 0 && (
                <div>
                  <p className="text-xs text-[#8A7F74] font-medium mb-1.5">Produktappetitt</p>
                  <div className="flex flex-wrap gap-1.5">
                    {insurer.appetite.map((p) => (
                      <span key={p} className="px-2 py-0.5 text-xs rounded-full bg-[#E8EDF5] text-[#4A6FA5]">
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {insurer.notes && (
                <div>
                  <p className="text-xs text-[#8A7F74] font-medium mb-1">Notater</p>
                  <p className="text-[#2C3E50] text-xs">{insurer.notes}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function InsurersPage() {
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
          <h1 className="text-2xl font-bold text-[#2C3E50]">Forsikringsselskaper</h1>
          <p className="text-sm text-[#8A7F74] mt-0.5">
            Administrer forsikringsselskaper og deres produktappetitt
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 px-4 py-2 bg-[#4A6FA5] text-white text-sm rounded-md hover:bg-[#3a5f95]"
        >
          {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          {showForm ? "Avbryt" : "Legg til"}
        </button>
      </div>

      {showForm && (
        <div className="broker-card">
          <p className="text-sm font-semibold text-[#2C3E50] mb-4">Nytt forsikringsselskap</p>
          <InsurerForm onSave={handleCreate} onCancel={() => setShowForm(false)} />
        </div>
      )}

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Søk etter selskap…"
        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
      />

      {isLoading && (
        <p className="text-sm text-[#8A7F74] text-center py-8">Laster…</p>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="text-center py-12 text-[#8A7F74]">
          <Building2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">
            {search ? "Ingen treff" : "Ingen forsikringsselskaper lagt til ennå"}
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
        <p className="text-xs text-[#8A7F74] text-center">
          {filtered.length} selskap{filtered.length !== 1 ? "er" : ""}
        </p>
      )}
    </div>
  );
}
