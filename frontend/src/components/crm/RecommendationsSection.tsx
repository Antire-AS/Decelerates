"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  FileText, Plus, Trash2, Download, ChevronDown, ChevronUp,
  CheckCircle, Loader2, X,
} from "lucide-react";
import {
  getOrgRecommendations, createRecommendation,
  deleteRecommendation, downloadRecommendationPdf,
  getOrgSubmissions, getInsurers,
  getOrgIdd,
  type Recommendation, type Submission, type Insurer, type IddBehovsanalyse,
} from "@/lib/api";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useT } from "@/lib/i18n";

// ── New recommendation form ───────────────────────────────────────────────────

function NewRecommendationForm({
  orgnr,
  onCreated,
  onCancel,
}: {
  orgnr: string;
  onCreated: () => void;
  onCancel: () => void;
}) {
  const T = useT();
  const { data: submissions = [] } = useSWR<Submission[]>(
    `submissions-${orgnr}`,
    () => getOrgSubmissions(orgnr),
  );
  const { data: insurers = [] } = useSWR<Insurer[]>("/insurers", getInsurers);
  const { data: iddList = [] } = useSWR<IddBehovsanalyse[]>(
    `idd-${orgnr}`,
    () => getOrgIdd(orgnr),
  );

  const [recommendedInsurer, setRecommendedInsurer] = useState("");
  const [selectedSubmissions, setSelectedSubmissions] = useState<number[]>([]);
  const [iddId, setIddId] = useState<number | "">("");
  const [rationale, setRationale] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const allSubs = submissions;

  function toggleSub(id: number) {
    setSelectedSubmissions((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!recommendedInsurer.trim()) return;
    setSaving(true);
    setErr(null);
    try {
      await createRecommendation(orgnr, {
        recommended_insurer: recommendedInsurer.trim(),
        submission_ids: selectedSubmissions.length ? selectedSubmissions : undefined,
        idd_id: iddId ? Number(iddId) : undefined,
        rationale_text: rationale.trim() || undefined,
      });
      onCreated();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="broker-card space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">{T("Ny forsikringsanbefaling")}</p>
        <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="rec-insurer">{T("Anbefalt forsikringsselskap")} *</label>
          <input
            id="rec-insurer"
            value={recommendedInsurer}
            onChange={(e) => setRecommendedInsurer(e.target.value)}
            required
            list="insurer-options"
            className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            placeholder={T("Velg eller skriv inn")}
          />
          <datalist id="insurer-options">
            {insurers.map((ins) => (
              <option key={ins.id} value={ins.name} />
            ))}
          </datalist>
        </div>
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="rec-idd">{T("Koble til behovsanalyse (IDD)")}</label>
          <select
            id="rec-idd"
            value={iddId}
            onChange={(e) => setIddId(e.target.value ? Number(e.target.value) : "")}
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="">{T("Ingen")}</option>
            {iddList.map((idd) => (
              <option key={idd.id} value={idd.id}>
                {idd.client_name || orgnr} — {new Date(idd.created_at).toLocaleDateString("nb-NO")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {allSubs.length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground font-medium">
            {T("Inkluder tilbud i sammenligningen")}
          </p>
          <div className="mt-1.5 space-y-1">
            {allSubs.map((sub) => (
              <label key={sub.id} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedSubmissions.includes(sub.id)}
                  onChange={() => toggleSub(sub.id)}
                  className="rounded"
                />
                <span className="text-xs text-foreground">
                  {sub.insurer_name ?? `${T("Selskap")} #${sub.insurer_id}`} · {sub.product_type}
                </span>
                <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                  sub.status === "quoted" ? "bg-blue-100 text-blue-700" :
                  sub.status === "declined" ? "bg-red-100 text-red-700" :
                  "bg-gray-100 text-gray-600"
                }`}>
                  {sub.status === "quoted" ? T("Tilbud") :
                   sub.status === "declined" ? T("Avslått") : T("Avventer")}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div>
        <label className="text-xs text-muted-foreground font-medium" htmlFor="rec-rationale">
          {T("Begrunnelse")}{" "}
          <span className="font-normal text-muted-foreground">
            {T("(la stå tom for å generere med AI)")}
          </span>
        </label>
        <textarea
          id="rec-rationale"
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={4}
          placeholder={T("Skriv begrunnelse manuelt, eller la feltet stå tomt for AI-generert tekst…")}
          className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
        />
      </div>

      {err && <p className="text-xs text-red-600">{err}</p>}

      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel}
          className="px-3 py-1.5 text-sm text-muted-foreground border border-gray-200 rounded-md hover:text-foreground">
          {T("Avbryt")}
        </button>
        <button type="submit" disabled={saving || !recommendedInsurer.trim()}
          className="px-4 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2">
          {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          {saving ? (rationale.trim() ? T("Lagrer…") : T("Genererer AI-begrunnelse…")) : T("Opprett anbefaling")}
        </button>
      </div>
    </form>
  );
}

// ── Recommendation card ───────────────────────────────────────────────────────

function RecommendationCard({
  rec,
  orgnr,
  onDeleted,
}: {
  rec: Recommendation;
  orgnr: string;
  onDeleted: () => void;
}) {
  const T = useT();
  const [open, setOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    try {
      await downloadRecommendationPdf(orgnr, rec.id);
    } finally {
      setDownloading(false);
    }
  }

  function handleDelete() {
    setConfirmDelete(true);
  }

  async function performDelete() {
    await deleteRecommendation(orgnr, rec.id);
    onDeleted();
  }

  const date = new Date(rec.created_at).toLocaleDateString("nb-NO");

  return (
    <div className="broker-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
            <p className="text-sm font-semibold text-foreground">
              {rec.recommended_insurer}
            </p>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 ml-6">
            {T("Utarbeidet")} {date}
            {rec.created_by_email && ` · ${rec.created_by_email}`}
            {rec.submission_ids && rec.submission_ids.length > 0 &&
              ` · ${rec.submission_ids.length} ${T("tilbud sammenlignet")}`}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            {downloading
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <Download className="w-3.5 h-3.5" />}
            {T("Last ned PDF")}
          </button>
          <button
            onClick={() => setOpen((v) => !v)}
            className="text-xs text-primary hover:underline flex items-center gap-1"
          >
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {open ? T("Skjul") : T("Vis")}
          </button>
          <button onClick={handleDelete} className="text-red-300 hover:text-red-500">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {open && rec.rationale_text && (
        <div className="mt-4 ml-6 p-3 bg-background rounded-lg border border-gray-100">
          <p className="text-xs text-muted-foreground font-medium mb-2">{T("Begrunnelse")}</p>
          <p className="text-sm text-foreground whitespace-pre-line leading-relaxed">
            {rec.rationale_text}
          </p>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={T("Slett anbefaling?")}
        description={T("Handlingen kan ikke angres.")}
        confirmLabel={T("Slett")}
        destructive
        onConfirm={performDelete}
      />
    </div>
  );
}

// ── Company picker + main view ────────────────────────────────────────────────

// Mounted inside the company profile CRM tab — orgnr comes from the URL
// route, not from a search input. Same form/list logic as the old standalone
// /recommendations page.
export default function RecommendationsSection({ orgnr }: { orgnr: string }) {
  const T = useT();
  const [showForm, setShowForm] = useState(false);

  const { data: recommendations = [], mutate } = useSWR<Recommendation[]>(
    `recommendations-${orgnr}`,
    () => getOrgRecommendations(orgnr),
  );

  return (
    <div className="broker-card space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <FileText className="w-4 h-4" /> {T("Anbefalingsbrev")} ({recommendations.length})
        </p>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
        >
          {showForm ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
          {showForm ? T("Avbryt") : T("Ny anbefaling")}
        </button>
      </div>

      {showForm && (
        <NewRecommendationForm
          orgnr={orgnr}
          onCreated={() => { mutate(); setShowForm(false); }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {recommendations.length === 0 && !showForm && (
        <div className="text-center py-6 text-muted-foreground">
          <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
          <p className="text-xs">{T("Ingen anbefalinger for denne klienten ennå.")}</p>
          <p className="text-xs mt-0.5">{T("Opprett en etter at tilbud er innhentet.")}</p>
        </div>
      )}

      <div className="space-y-2">
        {recommendations.map((rec) => (
          <RecommendationCard
            key={rec.id}
            rec={rec}
            orgnr={orgnr}
            onDeleted={mutate}
          />
        ))}
      </div>
    </div>
  );
}
