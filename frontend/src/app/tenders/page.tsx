"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getTenders,
  createTender,
  deleteTender,
  getInsurers,
  type TenderListItem,
  type Insurer,
} from "@/lib/api";
import {
  Plus,
  FileText,
  Trash2,
  Send,
  Clock,
  X,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft: { label: "Utkast", color: "bg-gray-100 text-gray-700" },
  sent: { label: "Sendt", color: "bg-blue-50 text-blue-700" },
  closed: { label: "Lukket", color: "bg-yellow-50 text-yellow-700" },
  analysed: { label: "Analysert", color: "bg-green-50 text-green-700" },
};

const PRODUCT_OPTIONS = [
  "Personalforsikring",
  "Yrkesskade",
  "Motorvogn",
  "Skadeforsikring",
  "Eiendomsforsikring",
  "Ansvarsforsikring",
  "Cyber",
  "Reiseforsikring",
  "Styreansvar (D&O)",
  "Kriminalitetsforsikring",
];

export default function TendersPage() {
  const { data: tenders, mutate } = useSWR<TenderListItem[]>("tenders", () => getTenders());
  const { data: insurers } = useSWR<Insurer[]>("insurers", getInsurers);
  const [showNew, setShowNew] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Anbud</h1>
          <p className="text-sm text-muted-foreground">Opprett og administrer anbudsforespørsler til forsikringsselskaper</p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80"
        >
          <Plus className="w-4 h-4" />
          Nytt anbud
        </button>
      </div>

      {/* Tender list */}
      {!tenders?.length ? (
        <div className="broker-card text-center py-12">
          <FileText className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
          <p className="text-muted-foreground">Ingen anbud ennå. Opprett ditt første anbud.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tenders.map((t) => {
            const s = STATUS_LABELS[t.status] || STATUS_LABELS.draft;
            return (
              <Link
                key={t.id}
                href={`/tenders/${t.id}`}
                className="broker-card flex items-center justify-between hover:shadow-md transition-shadow"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="font-semibold text-foreground">{t.title}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${s.color}`}>
                      {s.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>{t.product_types.join(", ")}</span>
                    {t.deadline && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Frist: {t.deadline}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-6 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Send className="w-3.5 h-3.5" />
                    {t.recipient_count} selskaper
                  </span>
                  <span className="flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" />
                    {t.offer_count} tilbud
                  </span>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      setDeleteId(t.id);
                    }}
                    className="p-1.5 hover:bg-red-50 rounded text-muted-foreground hover:text-red-500"
                    aria-label="Slett anbud"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* New tender modal */}
      {showNew && (
        <NewTenderModal
          insurers={insurers || []}
          onClose={() => setShowNew(false)}
          onCreated={() => {
            setShowNew(false);
            mutate();
          }}
        />
      )}

      <ConfirmDialog
        open={deleteId !== null}
        onOpenChange={(o) => { if (!o) setDeleteId(null); }}
        title="Slett dette anbudet?"
        description="Handlingen kan ikke angres."
        confirmLabel="Slett"
        destructive
        onConfirm={() => {
          if (deleteId !== null) {
            deleteTender(deleteId).then(() => mutate());
          }
        }}
      />
    </div>
  );
}

function NewTenderModal({
  insurers,
  onClose,
  onCreated,
}: {
  insurers: Insurer[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [orgnr, setOrgnr] = useState("");
  const [title, setTitle] = useState("");
  const [products, setProducts] = useState<string[]>([]);
  const [deadline, setDeadline] = useState("");
  const [notes, setNotes] = useState("");
  const [recipients, setRecipients] = useState<{ insurer_name: string; insurer_email?: string }[]>([]);
  const [saving, setSaving] = useState(false);

  const toggleProduct = (p: string) => {
    setProducts((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));
  };

  const addInsurer = (ins: Insurer) => {
    if (!recipients.find((r) => r.insurer_name === ins.name)) {
      setRecipients((prev) => [
        ...prev,
        { insurer_name: ins.name, insurer_email: ins.contact_email || undefined },
      ]);
    }
  };

  const removeRecipient = (name: string) => {
    setRecipients((prev) => prev.filter((r) => r.insurer_name !== name));
  };

  async function handleCreate() {
    if (!orgnr || !title || !products.length) return;
    setSaving(true);
    try {
      await createTender({
        orgnr,
        title,
        product_types: products,
        deadline: deadline || undefined,
        notes: notes || undefined,
        recipients,
      });
      onCreated();
    } catch {
      toast.error("Kunne ikke opprette anbud");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="bg-primary px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <h2 className="text-white font-semibold">Nytt anbud</h2>
          <button onClick={onClose} className="text-white/50 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Company */}
          <div>
            <label className="label-xs" htmlFor="tender-orgnr">Organisasjonsnummer</label>
            <input
              id="tender-orgnr"
              className="input-sm w-full"
              placeholder="F.eks. 984851006"
              value={orgnr}
              onChange={(e) => setOrgnr(e.target.value)}
            />
          </div>

          {/* Title */}
          <div>
            <label className="label-xs" htmlFor="tender-title">Tittel</label>
            <input
              id="tender-title"
              className="input-sm w-full"
              placeholder="F.eks. Totalforsikring 2026"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {/* Products */}
          <div>
            <p className="label-xs">Produkttyper</p>
            <div className="flex flex-wrap gap-2 mt-1">
              {PRODUCT_OPTIONS.map((p) => (
                <button
                  key={p}
                  onClick={() => toggleProduct(p)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    products.includes(p)
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-card text-muted-foreground border-border hover:border-primary"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Deadline */}
          <div>
            <label className="label-xs" htmlFor="tender-deadline">Anbudsfrist</label>
            <input
              id="tender-deadline"
              type="date"
              className="input-sm w-full"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
          </div>

          {/* Recipients from insurer directory */}
          <div>
            <p className="label-xs">Forsikringsselskaper (mottakere)</p>
            {recipients.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-1 mb-2">
                {recipients.map((r) => (
                  <span
                    key={r.insurer_name}
                    className="flex items-center gap-1 text-xs bg-accent text-foreground px-2 py-1 rounded-full"
                  >
                    {r.insurer_name}
                    <button onClick={() => removeRecipient(r.insurer_name)}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-2 mt-1">
              {insurers
                .filter((i) => !recipients.find((r) => r.insurer_name === i.name))
                .map((ins) => (
                  <button
                    key={ins.id}
                    onClick={() => addInsurer(ins)}
                    className="text-xs px-2.5 py-1 rounded-full border border-border text-muted-foreground hover:border-primary hover:text-primary"
                  >
                    + {ins.name}
                  </button>
                ))}
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="label-xs" htmlFor="tender-notes">Kravspesifikasjon / notater</label>
            <textarea
              id="tender-notes"
              className="input-sm w-full h-24 resize-none"
              placeholder="Beskriv krav, spesielle behov, osv."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">
              Avbryt
            </button>
            <button
              onClick={handleCreate}
              disabled={!orgnr || !title || !products.length || saving}
              className="px-6 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80 disabled:opacity-50"
            >
              {saving ? "Oppretter..." : "Opprett anbud"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
