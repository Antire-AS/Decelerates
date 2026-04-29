"use client";

import { useState } from "react";
import { createTender, type Insurer } from "@/lib/api";
import { X } from "lucide-react";
import { toast } from "sonner";
import { useT } from "@/lib/i18n";

const PRODUCT_OPTIONS = [
  "Personalforsikring", "Yrkesskade", "Motorvogn", "Skadeforsikring",
  "Eiendomsforsikring", "Ansvarsforsikring", "Cyber", "Reiseforsikring",
  "Styreansvar (D&O)", "Kriminalitetsforsikring",
];

export function NewTenderModal({
  insurers,
  onClose,
  onCreated,
}: {
  insurers: Insurer[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const T = useT();
  const [orgnr, setOrgnr] = useState("");
  const [title, setTitle] = useState("");
  const [products, setProducts] = useState<string[]>([]);
  const [deadline, setDeadline] = useState("");
  const [notes, setNotes] = useState("");
  const [recipients, setRecipients] = useState<{ insurer_name: string; insurer_email?: string }[]>([]);
  const [saving, setSaving] = useState(false);

  const toggleProduct = (p: string) =>
    setProducts((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));

  const addInsurer = (ins: Insurer) => {
    if (!recipients.find((r) => r.insurer_name === ins.name)) {
      setRecipients((prev) => [...prev, { insurer_name: ins.name, insurer_email: ins.contact_email || undefined }]);
    }
  };

  const removeRecipient = (name: string) =>
    setRecipients((prev) => prev.filter((r) => r.insurer_name !== name));

  async function handleCreate() {
    if (!orgnr || !title || !products.length) return;
    setSaving(true);
    try {
      await createTender({ orgnr, title, product_types: products, deadline: deadline || undefined, notes: notes || undefined, recipients });
      onCreated();
    } catch {
      toast.error(T("Kunne ikke opprette anbud"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="bg-primary px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <h2 className="text-white font-semibold">{T("Nytt anbud")}</h2>
          <button onClick={onClose} className="text-white/50 hover:text-white" aria-label={T("Lukk")}>
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 space-y-5">
          <div>
            <label className="label-xs" htmlFor="tender-orgnr">{T("Organisasjonsnummer")}</label>
            <input id="tender-orgnr" className="input-sm w-full" placeholder={T("F.eks. 984851006")} value={orgnr} onChange={(e) => setOrgnr(e.target.value)} />
          </div>
          <div>
            <label className="label-xs" htmlFor="tender-title">{T("Tittel")}</label>
            <input id="tender-title" className="input-sm w-full" placeholder={T("F.eks. Totalforsikring 2026")} value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <p className="label-xs">{T("Produkttyper")}</p>
            <div className="flex flex-wrap gap-2 mt-1">
              {PRODUCT_OPTIONS.map((p) => (
                <button key={p} onClick={() => toggleProduct(p)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${products.includes(p) ? "bg-primary text-primary-foreground border-primary" : "bg-card text-muted-foreground border-border hover:border-primary"}`}>
                  {T(p)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="label-xs" htmlFor="tender-deadline">{T("Anbudsfrist")}</label>
            <input id="tender-deadline" type="date" className="input-sm w-full" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
          </div>
          <div>
            <p className="label-xs">{T("Forsikringsselskaper (mottakere)")}</p>
            {recipients.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-1 mb-2">
                {recipients.map((r) => (
                  <span key={r.insurer_name} className="flex items-center gap-1 text-xs bg-accent text-foreground px-2 py-1 rounded-full">
                    {r.insurer_name}
                    <button onClick={() => removeRecipient(r.insurer_name)} aria-label={`Fjern ${r.insurer_name}`}><X className="w-3 h-3" /></button>
                  </span>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-2 mt-1">
              {insurers.filter((i) => !recipients.find((r) => r.insurer_name === i.name)).map((ins) => (
                <button key={ins.id} onClick={() => addInsurer(ins)}
                  className="text-xs px-2.5 py-1 rounded-full border border-border text-muted-foreground hover:border-primary hover:text-primary">
                  + {ins.name}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="label-xs" htmlFor="tender-notes">{T("Kravspesifikasjon / notater")}</label>
            <textarea id="tender-notes" className="input-sm w-full h-24 resize-none" placeholder={T("Beskriv krav, spesielle behov, osv.")} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">{T("Avbryt")}</button>
            <button onClick={handleCreate} disabled={!orgnr || !title || !products.length || saving}
              className="px-6 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80 disabled:opacity-50">
              {saving ? T("Oppretter...") : T("Opprett anbud")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
