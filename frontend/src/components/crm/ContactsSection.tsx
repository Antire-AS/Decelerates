"use client";

import { useState, useId } from "react";
import useSWR from "swr";
import {
  getOrgContacts, createContact, deleteContact,
  type Contact,
} from "@/lib/api";
import { Star, Trash2, Plus, ChevronDown, ChevronUp } from "lucide-react";

export default function ContactsSection({ orgnr }: { orgnr: string }) {
  const { data: contacts = [], mutate } = useSWR<Contact[]>(
    `contacts-${orgnr}`, () => getOrgContacts(orgnr),
  );
  const [open, setOpen]   = useState(false);
  const [form, setForm]   = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr]     = useState<string | null>(null);

  const [name, setName]     = useState("");
  const [title, setTitle]   = useState("");
  const [email, setEmail]   = useState("");
  const [phone, setPhone]   = useState("");
  const [primary, setPrimary] = useState(false);
  const [notes, setNotes]   = useState("");

  async function handleDelete(id: number) {
    await deleteContact(orgnr, id);
    mutate();
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setErr(null);
    try {
      await createContact(orgnr, {
        name, title: title || undefined, email: email || undefined,
        phone: phone || undefined, is_primary: primary, notes: notes || undefined,
      });
      setName(""); setTitle(""); setEmail(""); setPhone("");
      setPrimary(false); setNotes(""); setForm(false);
      mutate();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="broker-card">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]"
      >
        <span>👤 Kontaktpersoner {contacts.length > 0 && `(${contacts.length})`}</span>
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {contacts.length === 0 ? (
            <p className="text-xs text-[#8A7F74]">Ingen kontaktpersoner registrert.</p>
          ) : (
            <div className="divide-y divide-[#EDE8E3]">
              {contacts.map((c) => (
                <div key={c.id} className="flex items-start justify-between py-2 gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 text-sm font-medium text-[#2C3E50]">
                      {c.name}
                      {c.is_primary && <Star className="w-3 h-3 text-amber-500 fill-amber-400" />}
                    </div>
                    {c.title && <p className="text-xs text-[#8A7F74]">{c.title}</p>}
                    <p className="text-xs text-[#8A7F74]">
                      {[c.email, c.phone].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <button onClick={() => handleDelete(c.id)} className="text-[#C4BDB4] hover:text-red-500 flex-shrink-0">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {!form ? (
            <button
              onClick={() => setForm(true)}
              className="flex items-center gap-1 text-xs text-[#4A6FA5] hover:underline"
            >
              <Plus className="w-3 h-3" /> Legg til kontaktperson
            </button>
          ) : (
            <form onSubmit={handleAdd} className="space-y-2 pt-2 border-t border-[#EDE8E3]">
              <p className="text-xs font-semibold text-[#2C3E50]">Ny kontaktperson</p>
              <div className="grid grid-cols-2 gap-2">
                <Input label="Navn *"    value={name}  onChange={setName}  required />
                <Input label="Tittel"    value={title} onChange={setTitle} />
                <Input label="E-post"    value={email} onChange={setEmail} type="email" />
                <Input label="Telefon"   value={phone} onChange={setPhone} />
              </div>
              <label className="flex items-center gap-2 text-xs text-[#2C3E50] cursor-pointer">
                <input type="checkbox" checked={primary} onChange={(e) => setPrimary(e.target.checked)} className="accent-[#4A6FA5]" />
                Primærkontakt
              </label>
              <textarea
                value={notes} onChange={(e) => setNotes(e.target.value)}
                placeholder="Notater"
                rows={2}
                className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5]"
              />
              {err && <p className="text-xs text-red-600">{err}</p>}
              <div className="flex gap-2">
                <button type="submit" disabled={saving}
                  className="px-3 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50">
                  {saving ? "Lagrer…" : "Lagre"}
                </button>
                <button type="button" onClick={() => setForm(false)} className="px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#8A7F74]">
                  Avbryt
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}

function Input({ label, value, onChange, type = "text", required = false }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean;
}) {
  const id = useId();
  return (
    <div>
      <label className="block text-xs text-[#8A7F74] mb-0.5" htmlFor={id}>{label}</label>
      <input
        id={id} type={type} value={value} onChange={(e) => onChange(e.target.value)} required={required}
        className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded bg-white focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5]"
      />
    </div>
  );
}
