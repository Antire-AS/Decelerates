"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
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
import { searchCompanies } from "@/lib/api";

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

  const quotedSubs = submissions.filter((s) => s.status === "quoted");
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
        <p className="text-sm font-semibold text-[#2C3E50]">Ny forsikringsanbefaling</p>
        <button type="button" onClick={onCancel} className="text-[#8A7F74] hover:text-[#2C3E50]">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-[#8A7F74] font-medium">Anbefalt forsikringsselskap *</label>
          <input
            value={recommendedInsurer}
            onChange={(e) => setRecommendedInsurer(e.target.value)}
            required
            list="insurer-options"
            className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
            placeholder="Velg eller skriv inn"
          />
          <datalist id="insurer-options">
            {insurers.map((ins) => (
              <option key={ins.id} value={ins.name} />
            ))}
          </datalist>
        </div>
        <div>
          <label className="text-xs text-[#8A7F74] font-medium">Koble til behovsanalyse (IDD)</label>
          <select
            value={iddId}
            onChange={(e) => setIddId(e.target.value ? Number(e.target.value) : "")}
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
          >
            <option value="">Ingen</option>
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
          <label className="text-xs text-[#8A7F74] font-medium">
            Inkluder tilbud i sammenligningen
          </label>
          <div className="mt-1.5 space-y-1">
            {allSubs.map((sub) => (
              <label key={sub.id} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedSubmissions.includes(sub.id)}
                  onChange={() => toggleSub(sub.id)}
                  className="rounded"
                />
                <span className="text-xs text-[#2C3E50]">
                  {sub.insurer_name ?? `Selskap #${sub.insurer_id}`} · {sub.product_type}
                </span>
                <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                  sub.status === "quoted" ? "bg-blue-100 text-blue-700" :
                  sub.status === "declined" ? "bg-red-100 text-red-700" :
                  "bg-gray-100 text-gray-600"
                }`}>
                  {sub.status === "quoted" ? "Tilbud" :
                   sub.status === "declined" ? "Avslått" : "Avventer"}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div>
        <label className="text-xs text-[#8A7F74] font-medium">
          Begrunnelse{" "}
          <span className="font-normal text-[#8A7F74]">
            (la stå tom for å generere med AI)
          </span>
        </label>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={4}
          placeholder="Skriv begrunnelse manuelt, eller la feltet stå tomt for AI-generert tekst…"
          className="w-full mt-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] resize-none"
        />
      </div>

      {err && <p className="text-xs text-red-600">{err}</p>}

      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel}
          className="px-3 py-1.5 text-sm text-[#8A7F74] border border-gray-200 rounded-md hover:text-[#2C3E50]">
          Avbryt
        </button>
        <button type="submit" disabled={saving || !recommendedInsurer.trim()}
          className="px-4 py-1.5 text-sm bg-[#4A6FA5] text-white rounded-md hover:bg-[#3a5f95] disabled:opacity-50 flex items-center gap-2">
          {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          {saving ? (rationale.trim() ? "Lagrer…" : "Genererer AI-begrunnelse…") : "Opprett anbefaling"}
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
  const [open, setOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    try {
      await downloadRecommendationPdf(orgnr, rec.id);
    } finally {
      setDownloading(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Slett anbefaling?")) return;
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
            <p className="text-sm font-semibold text-[#2C3E50]">
              {rec.recommended_insurer}
            </p>
          </div>
          <p className="text-xs text-[#8A7F74] mt-0.5 ml-6">
            Utarbeidet {date}
            {rec.created_by_email && ` · ${rec.created_by_email}`}
            {rec.submission_ids && rec.submission_ids.length > 0 &&
              ` · ${rec.submission_ids.length} tilbud sammenlignet`}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#4A6FA5] text-white rounded-md hover:bg-[#3a5f95] disabled:opacity-50"
          >
            {downloading
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <Download className="w-3.5 h-3.5" />}
            Last ned PDF
          </button>
          <button
            onClick={() => setOpen((v) => !v)}
            className="text-xs text-[#4A6FA5] hover:underline flex items-center gap-1"
          >
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {open ? "Skjul" : "Vis"}
          </button>
          <button onClick={handleDelete} className="text-red-300 hover:text-red-500">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {open && rec.rationale_text && (
        <div className="mt-4 ml-6 p-3 bg-[#F8F9FB] rounded-lg border border-gray-100">
          <p className="text-xs text-[#8A7F74] font-medium mb-2">Begrunnelse</p>
          <p className="text-sm text-[#2C3E50] whitespace-pre-line leading-relaxed">
            {rec.rationale_text}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Company picker + main view ────────────────────────────────────────────────

function RecommendationsContent() {
  const searchParams = useSearchParams();
  const initialOrgnr = searchParams.get("orgnr") ?? "";

  const [orgnr, setOrgnr] = useState(initialOrgnr);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{ orgnr: string; navn: string }[]>([]);
  const [searching, setSearching] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const { data: recommendations = [], mutate } = useSWR<Recommendation[]>(
    orgnr ? `recommendations-${orgnr}` : null,
    () => getOrgRecommendations(orgnr),
  );

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const results = await searchCompanies(searchQuery, 8);
      setSearchResults(results);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Anbefalingsbrev</h1>
        <p className="text-sm text-[#8A7F74] mt-0.5">
          Generer formell forsikringsanbefaling til klient med AI-begrunnelse
        </p>
      </div>

      {/* Company selector */}
      <div className="broker-card space-y-3">
        <p className="text-sm font-semibold text-[#2C3E50]">Velg klient</p>
        <div className="flex gap-2">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Søk på selskapsnavn…"
            className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
          />
          <button
            onClick={handleSearch}
            disabled={searching}
            className="px-3 py-1.5 text-sm bg-[#4A6FA5] text-white rounded-md hover:bg-[#3a5f95] disabled:opacity-50"
          >
            {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : "Søk"}
          </button>
        </div>

        {searchResults.length > 0 && (
          <div className="divide-y divide-gray-100 border border-gray-200 rounded-md overflow-hidden">
            {searchResults.map((r) => (
              <button
                key={r.orgnr}
                onClick={() => { setOrgnr(r.orgnr); setSearchResults([]); setSearchQuery(r.navn); }}
                className={`w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-[#F0F4FB] text-left ${
                  orgnr === r.orgnr ? "bg-[#E8EDF5]" : "bg-white"
                }`}
              >
                <span className="font-medium text-[#2C3E50]">{r.navn}</span>
                <span className="text-xs text-[#8A7F74]">{r.orgnr}</span>
              </button>
            ))}
          </div>
        )}

        {orgnr && (
          <p className="text-xs text-[#8A7F74]">
            Valgt org.nr: <span className="font-medium text-[#2C3E50]">{orgnr}</span>
          </p>
        )}
      </div>

      {orgnr && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-[#2C3E50]">
              Anbefalinger ({recommendations.length})
            </p>
            <button
              onClick={() => setShowForm((v) => !v)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm bg-[#4A6FA5] text-white rounded-md hover:bg-[#3a5f95]"
            >
              {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
              {showForm ? "Avbryt" : "Ny anbefaling"}
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
            <div className="text-center py-12 text-[#8A7F74]">
              <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">Ingen anbefalinger for denne klienten ennå</p>
              <p className="text-xs mt-1">
                Opprett en anbefaling etter at tilbud er innhentet
              </p>
            </div>
          )}

          <div className="space-y-3">
            {recommendations.map((rec) => (
              <RecommendationCard
                key={rec.id}
                rec={rec}
                orgnr={orgnr}
                onDeleted={mutate}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function RecommendationsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-[#4A6FA5]" />
      </div>
    }>
      <RecommendationsContent />
    </Suspense>
  );
}
