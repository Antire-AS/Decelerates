"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import {
  getOrgCoverageAnalyses,
  uploadCoverageAnalysis,
  deleteCoverageAnalysis,
  type CoverageAnalysis,
} from "@/lib/api";
import { fmtNok } from "@/lib/format";
import {
  Trash2,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  ChevronDown,
  ChevronRight,
  Loader2,
} from "lucide-react";

interface CoverageSectionProps {
  orgnr: string;
}

export default function CoverageSection({ orgnr }: CoverageSectionProps) {
  const { data: analyses, mutate } = useSWR<CoverageAnalysis[]>(
    `coverage-${orgnr}`,
    () => getOrgCoverageAnalyses(orgnr)
  );
  const [uploading, setUploading] = useState(false);
  const [title, setTitle] = useState("");
  const [insurer, setInsurer] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadCoverageAnalysis(orgnr, file, {
        title: title || file.name.replace(".pdf", ""),
        insurer: insurer || undefined,
      });
      setTitle("");
      setInsurer("");
      mutate();
    } catch {
      alert("Kunne ikke analysere dokumentet");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-bold text-[#2C3E50] flex items-center gap-2">
          <Shield className="w-5 h-5 text-[#4A6FA5]" />
          Dekningsanalyse
        </h3>
      </div>

      {/* Upload form */}
      <div className="broker-card">
        <p className="text-sm text-[#8A7F74] mb-3">
          Last opp et forsikringsdokument (polise, vilkår, tilbud) for AI-analyse av dekningsomfang.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
          <input
            className="input-sm"
            placeholder="Tittel (f.eks. Ansvarsforsikring 2026)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <input
            className="input-sm"
            placeholder="Forsikringsgiver (f.eks. If)"
            value={insurer}
            onChange={(e) => setInsurer(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            onChange={handleUpload}
            disabled={uploading}
            className="block flex-1 text-sm text-[#8A7F74] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:bg-[#2C3E50] file:text-white hover:file:bg-[#1a252f] disabled:opacity-50"
          />
          {uploading && (
            <span className="text-xs text-[#4A6FA5] flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              Analyserer...
            </span>
          )}
        </div>
      </div>

      {/* Results */}
      {!analyses?.length ? (
        <div className="text-center py-8 text-sm text-[#8A7F74]">
          Ingen dekningsanalyser ennå. Last opp et forsikringsdokument for å komme i gang.
        </div>
      ) : (
        <div className="space-y-3">
          {analyses.map((a) => (
            <CoverageCard key={a.id} analysis={a} onDelete={() => {
              deleteCoverageAnalysis(a.id).then(() => mutate());
            }} />
          ))}
        </div>
      )}
    </div>
  );
}

function CoverageCard({ analysis, onDelete }: { analysis: CoverageAnalysis; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const cd = analysis.coverage_data as CoverageData | undefined;

  return (
    <div className="broker-card">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          {analysis.status === "analysed" ? (
            <ShieldCheck className="w-5 h-5 text-[#5A8A5A]" />
          ) : analysis.status === "error" ? (
            <ShieldX className="w-5 h-5 text-[#C0392B]" />
          ) : (
            <Loader2 className="w-5 h-5 text-[#C8A951] animate-spin" />
          )}
          <div>
            <h4 className="text-sm font-semibold text-[#2C3E50]">{analysis.title}</h4>
            <div className="flex items-center gap-3 text-xs text-[#8A7F74]">
              {analysis.insurer && <span>{analysis.insurer}</span>}
              {analysis.product_type && <span>· {analysis.product_type}</span>}
              {analysis.premium_nok != null && <span>· Premie: {fmtNok(analysis.premium_nok)}</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); if (confirm("Slett denne analysen?")) onDelete(); }}
            className="p-1 hover:bg-red-50 rounded text-[#8A7F74] hover:text-red-500"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          {expanded ? <ChevronDown className="w-4 h-4 text-[#8A7F74]" /> : <ChevronRight className="w-4 h-4 text-[#8A7F74]" />}
        </div>
      </div>

      {expanded && cd && (
        <div className="mt-4 pt-4 border-t border-[#EDE8E3] space-y-4">
          {/* Summary */}
          {cd.oppsummering && (
            <p className="text-sm text-[#8A7F74] italic">{cd.oppsummering}</p>
          )}

          {/* Key figures */}
          <div className="grid grid-cols-3 gap-3">
            {analysis.premium_nok != null && (
              <div className="text-center p-3 bg-[#F5F0EB] rounded-lg">
                <div className="text-xs text-[#8A7F74]">Premie</div>
                <div className="text-base font-bold text-[#2C3E50]">{fmtNok(analysis.premium_nok)}</div>
              </div>
            )}
            {analysis.deductible_nok != null && (
              <div className="text-center p-3 bg-[#F5F0EB] rounded-lg">
                <div className="text-xs text-[#8A7F74]">Egenandel</div>
                <div className="text-base font-bold text-[#2C3E50]">{fmtNok(analysis.deductible_nok)}</div>
              </div>
            )}
            {analysis.coverage_sum_nok != null && (
              <div className="text-center p-3 bg-[#F5F0EB] rounded-lg">
                <div className="text-xs text-[#8A7F74]">Forsikringssum</div>
                <div className="text-base font-bold text-[#2C3E50]">{fmtNok(analysis.coverage_sum_nok)}</div>
              </div>
            )}
          </div>

          {/* Coverage items */}
          {cd.dekninger && cd.dekninger.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold text-[#2C3E50] uppercase tracking-wide mb-2">Dekninger</h5>
              <div className="space-y-2">
                {cd.dekninger.map((d, i) => (
                  <div key={i} className="p-3 bg-[#F5F0EB] rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-semibold text-[#2C3E50]">{d.navn}</span>
                      {d.sum_nok != null && d.sum_nok > 0 && (
                        <span className="text-xs text-[#4A6FA5] font-medium">{fmtNok(d.sum_nok)}</span>
                      )}
                    </div>
                    {d.beskrivelse && <p className="text-xs text-[#8A7F74]">{d.beskrivelse}</p>}
                    <div className="flex gap-4 mt-1 text-xs text-[#8A7F74]">
                      {d.egenandel_nok != null && d.egenandel_nok > 0 && <span>Egenandel: {fmtNok(d.egenandel_nok)}</span>}
                      {d.karenstid && <span>Karenstid: {d.karenstid}</span>}
                      {d.begrensninger && <span>Begrensning: {d.begrensninger}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Exclusions */}
          {cd.unntak && cd.unntak.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold text-[#C0392B] uppercase tracking-wide mb-2 flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5" />
                Unntak (ikke dekket)
              </h5>
              <ul className="space-y-1">
                {cd.unntak.map((u, i) => (
                  <li key={i} className="text-sm text-[#8A7F74] flex items-start gap-2">
                    <ShieldX className="w-3.5 h-3.5 text-[#C0392B] mt-0.5 flex-shrink-0" />
                    {u}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Special terms */}
          {cd.særvilkår && cd.særvilkår.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold text-[#C8A951] uppercase tracking-wide mb-2">Særvilkår</h5>
              <ul className="space-y-1">
                {cd.særvilkår.map((s, i) => (
                  <li key={i} className="text-sm text-[#8A7F74]">• {s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface CoverageItem {
  navn: string;
  beskrivelse?: string;
  sum_nok?: number;
  egenandel_nok?: number;
  karenstid?: string;
  begrensninger?: string;
}

interface CoverageData {
  forsikringstype?: string;
  forsikringsgiver?: string;
  polisenummer?: string;
  gyldig_fra?: string;
  gyldig_til?: string;
  premie_nok?: number;
  egenandel_nok?: number;
  forsikringssum_nok?: number;
  dekninger?: CoverageItem[];
  unntak?: string[];
  særvilkår?: string[];
  oppsummering?: string;
}
