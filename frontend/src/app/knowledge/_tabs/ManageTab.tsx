"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  BookOpen, FileText, Video, Loader2, RefreshCw, Sparkles, Plus,
} from "lucide-react";
import {
  knowledgeIndex, knowledgeSeedRegulations,
  getKnowledgeStats, knowledgeIngest,
} from "@/lib/api";

export default function ManageTab() {
  const { data: stats, mutate: mutateStats } = useSWR("knowledge-stats", getKnowledgeStats);

  const [indexLoading, setIndexLoading]   = useState(false);
  const [indexResult, setIndexResult]     = useState<string | null>(null);
  const [indexErr, setIndexErr]           = useState<string | null>(null);

  const [seedLoading, setSeedLoading]     = useState(false);
  const [seedResult, setSeedResult]       = useState<Array<{ name: string; status: string; chunks?: number }> | null>(null);
  const [seedErr, setSeedErr]             = useState<string | null>(null);

  // Custom ingest form
  const [ingestOrgnr,  setIngestOrgnr]  = useState("");
  const [ingestSource, setIngestSource] = useState("custom_note");
  const [ingestText,   setIngestText]   = useState("");
  const [ingestLoading, setIngestLoading] = useState(false);
  const [ingestErr,    setIngestErr]    = useState<string | null>(null);
  const [ingestOk,     setIngestOk]     = useState<string | null>(null);

  async function handleIngest() {
    setIngestErr(null);
    setIngestOk(null);
    const orgnr = ingestOrgnr.trim();
    if (!/^\d{9}$/.test(orgnr)) {
      setIngestErr("Skriv inn et gyldig 9-sifret orgnr.");
      return;
    }
    if (!ingestText.trim()) {
      setIngestErr("Teksten kan ikke være tom.");
      return;
    }
    setIngestLoading(true);
    try {
      const r = await knowledgeIngest(orgnr, ingestText.trim(), ingestSource.trim() || "custom_note");
      setIngestOk(`Lagret ${r.chunks_stored} biter for orgnr ${r.orgnr}.`);
      setIngestText("");
      mutateStats();
    } catch (e) {
      setIngestErr(String(e));
    } finally {
      setIngestLoading(false);
    }
  }

  async function handleIndex(force: boolean) {
    setIndexLoading(true); setIndexResult(null); setIndexErr(null);
    try {
      const r = await knowledgeIndex(force);
      setIndexResult(
        `Indeksering fullført — ${r.total_new_chunks} nye chunks ` +
        `(${r.docs_chunks} dokumenter, ${r.video_chunks} videoer)` +
        (r.cleared_chunks != null ? `, slettet ${r.cleared_chunks}` : ""),
      );
      mutateStats();
    } catch (e) { setIndexErr(String(e)); }
    finally { setIndexLoading(false); }
  }

  async function handleSeedRegulations() {
    setSeedLoading(true); setSeedResult(null); setSeedErr(null);
    try {
      const r = await knowledgeSeedRegulations();
      setSeedResult(r.seeded);
      mutateStats();
    } catch (e) { setSeedErr(String(e)); }
    finally { setSeedLoading(false); }
  }

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Totalt chunks", value: stats?.total_chunks, icon: <BookOpen className="w-4 h-4" /> },
          { label: "Dokumentchunks", value: stats?.doc_chunks,   icon: <FileText className="w-4 h-4" /> },
          { label: "Videochunks",    value: stats?.video_chunks,  icon: <Video className="w-4 h-4" /> },
        ].map(({ label, value, icon }) => (
          <div key={label} className="broker-card text-center">
            <div className="flex justify-center text-[#4A6FA5] mb-1">{icon}</div>
            <p className="text-xl font-bold text-[#2C3E50]">{value ?? "–"}</p>
            <p className="text-xs text-[#8A7F74]">{label}</p>
          </div>
        ))}
      </div>

      {/* Index documents */}
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
          <RefreshCw className="w-4 h-4" /> Indekser dokumenter og videoer
        </h3>
        <p className="text-xs text-[#8A7F74]">
          Henter alle dokumenter og videoer fra databasen og bygger vektorsøkeindeksen på nytt.
          Bruk &ldquo;Tving&rdquo; for å slette eksisterende indeks og starte fra scratch.
        </p>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => handleIndex(false)}
            disabled={indexLoading}
            className="px-3 py-1.5 text-xs rounded-lg bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1.5"
          >
            {indexLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Indekser (inkrementelt)
          </button>
          <button
            onClick={() => handleIndex(true)}
            disabled={indexLoading}
            className="px-3 py-1.5 text-xs rounded-lg bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 disabled:opacity-50 flex items-center gap-1.5"
          >
            {indexLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Tving full re-indeksering
          </button>
        </div>
        {indexErr    && <p className="text-xs text-red-600">{indexErr}</p>}
        {indexResult && <p className="text-xs text-green-700">{indexResult}</p>}
      </div>

      {/* Seed regulations */}
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
          <Sparkles className="w-4 h-4" /> Seed norske forsikringsreguleringer
        </h3>
        <p className="text-xs text-[#8A7F74]">
          Legger til forhåndsdefinererte norske forsikrings- og finansreguleringer i kunnskapsbasen
          (GDPR, IDD, Solvens II, m.fl.). Allerede eksisterende oppføringer hoppes over.
        </p>
        <button
          onClick={handleSeedRegulations}
          disabled={seedLoading}
          className="px-3 py-1.5 text-xs rounded-lg bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1.5"
        >
          {seedLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
          Seed reguleringer
        </button>
        {seedErr && <p className="text-xs text-red-600">{seedErr}</p>}
        {seedResult && (
          <div className="divide-y divide-[#EDE8E3]">
            {seedResult.map((item, i) => (
              <div key={i} className="py-2 flex items-center justify-between text-xs">
                <span className="text-[#2C3E50] font-medium">{item.name}</span>
                <div className="flex items-center gap-2 text-[#8A7F74]">
                  {item.chunks != null && <span>{item.chunks} chunks</span>}
                  <span className={`px-1.5 py-0.5 rounded-full ${
                    item.status === "seeded" ? "bg-green-100 text-green-700"
                    : item.status === "exists" ? "bg-[#EDE8E3] text-[#8A7F74]"
                    : "bg-red-100 text-red-600"
                  }`}>
                    {item.status === "seeded" ? "Lagt til" : item.status === "exists" ? "Finnes" : item.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Custom knowledge ingest form */}
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Legg til egendefinert tekst
        </h3>
        <p className="text-xs text-[#8A7F74]">
          Teksten blir delt opp i biter og embeddet for bruk i AI-chat. Knyttes til et orgnr.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div>
            <label className="block text-xs font-medium text-[#8A7F74] mb-1">Orgnr (9 siffer)</label>
            <input
              value={ingestOrgnr}
              onChange={(e) => setIngestOrgnr(e.target.value.replace(/\D/g, "").slice(0, 9))}
              maxLength={9}
              placeholder="123456789"
              className="w-full px-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#8A7F74] mb-1">Kildelabel</label>
            <input
              value={ingestSource}
              onChange={(e) => setIngestSource(e.target.value)}
              placeholder="custom_note"
              className="w-full px-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-[#8A7F74] mb-1">Tekst å legge inn</label>
          <textarea
            value={ingestText}
            onChange={(e) => setIngestText(e.target.value)}
            rows={5}
            placeholder="Lim inn notater, sammendrag eller fritekst…"
            className="w-full px-3 py-2 text-sm border border-[#D4C9B8] rounded-lg text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] resize-y"
          />
        </div>
        <button
          onClick={handleIngest}
          disabled={ingestLoading}
          className="px-3 py-1.5 text-xs rounded-lg bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1.5"
        >
          {ingestLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
          Lagre i kunnskapsbase
        </button>
        {ingestErr && <p className="text-xs text-red-600">{ingestErr}</p>}
        {ingestOk  && <p className="text-xs text-green-700">{ingestOk}</p>}
      </div>
    </div>
  );
}
