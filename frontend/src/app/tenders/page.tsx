"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getTenders,
  createTender,
  deleteTender,
  getInsurers,
  getInsuranceProducts,
  type TenderListItem,
  type Insurer,
  type InsuranceProductOut,
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
import { useT } from "@/lib/i18n";

const STATUS_KEYS: Record<string, { labelKey: string; color: string }> = {
  draft: { labelKey: "Utkast", color: "bg-gray-100 text-gray-700" },
  sent: { labelKey: "Sendt", color: "bg-blue-50 text-blue-700" },
  closed: { labelKey: "Lukket", color: "bg-yellow-50 text-yellow-700" },
  analysed: { labelKey: "Analysert", color: "bg-green-50 text-green-700" },
};

// Fallback product list — used when the catalog API returns nothing
// (e.g. fresh DB before the seed has run, or API offline). Once the
// catalog is populated, the picker shows ~45 products grouped by
// category instead of these 10 flat tags.
const FALLBACK_PRODUCTS = [
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

const CATEGORY_LABEL: Record<string, string> = {
  personell: "Personell",
  bygning: "Bygning og innhold",
  ansvar: "Ansvar",
  drift: "Drift / driftsavbrudd",
  transport: "Transport og kjøretøy",
  marine: "Marine",
  annet: "Annet",
};

export default function TendersPage() {
  const T = useT();
  const { data: tenders, mutate } = useSWR<TenderListItem[]>("tenders", () => getTenders());
  const { data: insurers } = useSWR<Insurer[]>("insurers", getInsurers);
  const [showNew, setShowNew] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{T("Anbud")}</h1>
          <p className="text-sm text-muted-foreground">{T("Opprett og administrer anbudsforespørsler til forsikringsselskaper")}</p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80"
        >
          <Plus className="w-4 h-4" />
          {T("Nytt anbud")}
        </button>
      </div>

      {/* Tender list */}
      {!tenders?.length ? (
        <div className="broker-card text-center py-12">
          <FileText className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
          <p className="text-muted-foreground">{T("Ingen anbud ennå. Opprett ditt første anbud.")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tenders.map((t) => {
            const s = STATUS_KEYS[t.status] || STATUS_KEYS.draft;
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
                      {T(s.labelKey)}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>{t.product_types.join(", ")}</span>
                    {t.deadline && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {T("Frist")}: {t.deadline}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-6 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Send className="w-3.5 h-3.5" />
                    {t.recipient_count} {T("selskaper")}
                  </span>
                  <span className="flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" />
                    {t.offer_count} {T("tilbud")}
                  </span>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      setDeleteId(t.id);
                    }}
                    className="p-1.5 hover:bg-red-50 rounded text-muted-foreground hover:text-red-500"
                    aria-label={T("Slett anbud")}
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
        title={T("Slett dette anbudet?")}
        description={T("Handlingen kan ikke angres.")}
        confirmLabel={T("Slett")}
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
  const T = useT();
  const [orgnr, setOrgnr] = useState("");
  const [title, setTitle] = useState("");
  const [products, setProducts] = useState<string[]>([]);
  const [deadline, setDeadline] = useState("");
  const [notes, setNotes] = useState("");
  const { data: catalog } = useSWR<InsuranceProductOut[]>(
    "insurance-products",
    () => getInsuranceProducts(),
  );
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
          <button onClick={onClose} className="text-white/50 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Company */}
          <div>
            <label className="label-xs" htmlFor="tender-orgnr">{T("Organisasjonsnummer")}</label>
            <input
              id="tender-orgnr"
              className="input-sm w-full"
              placeholder={T("F.eks. 984851006")}
              value={orgnr}
              onChange={(e) => setOrgnr(e.target.value)}
            />
          </div>

          {/* Title */}
          <div>
            <label className="label-xs" htmlFor="tender-title">{T("Tittel")}</label>
            <input
              id="tender-title"
              className="input-sm w-full"
              placeholder={T("F.eks. Totalforsikring 2026")}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {/* Products — grouped by category from the seeded catalog;
              falls back to a flat list if the catalog API returns nothing. */}
          <ProductPicker
            catalog={catalog}
            selected={products}
            onToggle={toggleProduct}
            T={T}
          />

          {/* Deadline */}
          <div>
            <label className="label-xs" htmlFor="tender-deadline">{T("Anbudsfrist")}</label>
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
            <p className="label-xs">{T("Forsikringsselskaper (mottakere)")}</p>
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
            <label className="label-xs" htmlFor="tender-notes">{T("Kravspesifikasjon / notater")}</label>
            <textarea
              id="tender-notes"
              className="input-sm w-full h-24 resize-none"
              placeholder={T("Beskriv krav, spesielle behov, osv.")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">
              {T("Avbryt")}
            </button>
            <button
              onClick={handleCreate}
              disabled={!orgnr || !title || !products.length || saving}
              className="px-6 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80 disabled:opacity-50"
            >
              {saving ? T("Oppretter...") : T("Opprett anbud")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProductPicker({
  catalog,
  selected,
  onToggle,
  T,
}: {
  catalog: InsuranceProductOut[] | undefined;
  selected: string[];
  onToggle: (name: string) => void;
  T: (s: string) => string;
}) {
  // Empty / loading: show the flat fallback list.
  if (!catalog || catalog.length === 0) {
    return (
      <div>
        <p className="label-xs">{T("Produkttyper")}</p>
        <div className="flex flex-wrap gap-2 mt-1">
          {FALLBACK_PRODUCTS.map((p) => (
            <button
              key={p}
              onClick={() => onToggle(p)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                selected.includes(p)
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-card text-muted-foreground border-border hover:border-primary"
              }`}
            >
              {T(p)}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // Group products by category, preserving the catalog's stable sort order.
  const groups: Record<string, InsuranceProductOut[]> = {};
  for (const p of catalog) {
    (groups[p.category] ||= []).push(p);
  }

  return (
    <div>
      <p className="label-xs">{T("Produkttyper")}</p>
      <div className="space-y-3 mt-1">
        {Object.keys(groups).map((cat) => (
          <div key={cat}>
            <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground mb-1">
              {T(CATEGORY_LABEL[cat] ?? cat)}
            </p>
            <div className="flex flex-wrap gap-2">
              {groups[cat].map((p) => (
                <button
                  key={p.id}
                  onClick={() => onToggle(p.name)}
                  title={p.description ?? undefined}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    selected.includes(p.name)
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-card text-muted-foreground border-border hover:border-primary"
                  }`}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
