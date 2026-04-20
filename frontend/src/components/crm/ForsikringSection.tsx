"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getOrgInsuranceNeeds, generateRiskOffer, generateNarrative,
  getOrgOffers, updateOfferStatus, deleteOffer, uploadOrgOffers,
  type InsuranceNeed, type InsuranceOffer, type RiskOfferOut,
} from "@/lib/api";
import { Loader2, Trash2, ChevronDown, ChevronUp, Sparkles, FileText, Upload } from "lucide-react";
import { fmtNok } from "@/lib/format";
import CoverageGapSection from "@/components/crm/CoverageGapSection";
import { useT } from "@/lib/i18n";

const PRIORITY_COLOR: Record<string, string> = {
  critical: "text-red-600", high: "text-orange-500",
  medium: "text-yellow-600", low: "text-green-700",
};

function fmtRange(r?: { low: number; mid: number; high: number }) {
  if (!r) return "–";
  return `${fmtNok(r.low)} – ${fmtNok(r.high)}`;
}

export default function ForsikringSection({ orgnr }: { orgnr: string }) {
  const T = useT();
  const PRIORITY_LABEL: Record<string, string> = {
    critical: T("Kritisk"), high: T("Høy"), medium: T("Middels"), low: T("Lav"),
  };
  const OFFER_STATUS_LABEL: Record<string, string> = {
    pending: T("Venter"), reviewed: T("Gjennomgått"), accepted: T("Akseptert"), rejected: T("Avvist"),
  };
  const { data: needsData, isLoading: needsLoading } = useSWR(
    `needs-${orgnr}`, () => getOrgInsuranceNeeds(orgnr),
  );
  const { data: offers = [], mutate: mutateOffers } = useSWR<InsuranceOffer[]>(
    `offers-${orgnr}`, () => getOrgOffers(orgnr),
  );

  const [needsOpen, setNeedsOpen]       = useState(true);
  const [narrativeOpen, setNarrativeOpen] = useState(false);
  const [offersOpen, setOffersOpen]     = useState(false);

  const [narrative, setNarrative]   = useState<string | null>(null);
  const [riskOffer, setRiskOffer]   = useState<RiskOfferOut | null>(null);
  const [genLoading, setGenLoading] = useState(false);
  const [genErr, setGenErr]         = useState<string | null>(null);

  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [uploading, setUploading]     = useState(false);
  const [uploadErr, setUploadErr]     = useState<string | null>(null);
  const [uploadOpen, setUploadOpen]   = useState(false);

  async function handleUpload() {
    if (!uploadFiles?.length) return;
    setUploading(true); setUploadErr(null);
    try {
      await uploadOrgOffers(orgnr, Array.from(uploadFiles));
      setUploadFiles(null); setUploadOpen(false);
      mutateOffers();
    } catch (e) { setUploadErr(String(e)); }
    finally { setUploading(false); }
  }

  async function handleGenerateNarrative() {
    setGenLoading(true); setGenErr(null);
    try {
      const r = await generateNarrative(orgnr);
      setNarrative(r.narrative);
      setNarrativeOpen(true);
    } catch (e) { setGenErr(String(e)); }
    finally { setGenLoading(false); }
  }

  async function handleGenerateOffer() {
    setGenLoading(true); setGenErr(null);
    try {
      const r = await generateRiskOffer(orgnr);
      setRiskOffer(r);
      setNarrativeOpen(true);
    } catch (e) { setGenErr(String(e)); }
    finally { setGenLoading(false); }
  }

  async function handleDeleteOffer(id: number) {
    await deleteOffer(orgnr, id);
    mutateOffers();
  }

  async function handleStatusChange(id: number, status: string) {
    await updateOfferStatus(orgnr, id, status);
    mutateOffers();
  }

  const needs: InsuranceNeed[] = needsData?.needs ?? [];

  return (
    <div className="space-y-2">
      <CoverageGapSection orgnr={orgnr} />
      {/* Insurance needs */}
      <div className="broker-card">
        <button onClick={() => setNeedsOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-foreground">
          <span>🛡️ {T("Forsikringsbehov")} {needs.length > 0 && `(${needs.length})`}</span>
          {needsOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {needsOpen && (
          <div className="mt-3">
            {needsLoading ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" /> {T("Estimerer…")}
              </div>
            ) : needs.length === 0 ? (
              <p className="text-xs text-muted-foreground">{T("Ingen behovsdata tilgjengelig.")}</p>
            ) : (
              <>
                {needsData?.narrative && (
                  <p className="text-xs text-muted-foreground mb-3 italic">{needsData.narrative}</p>
                )}
                <div className="divide-y divide-border">
                  {needs.map((n, i) => (
                    <div key={i} className="py-2.5">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold text-foreground">{n.type}</p>
                        <span className={`text-xs font-medium ${PRIORITY_COLOR[n.priority] ?? "text-muted-foreground"}`}>
                          {PRIORITY_LABEL[n.priority] ?? n.priority}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{n.reason}</p>
                      {(n.estimated_coverage_nok || n.estimated_annual_premium_nok) && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {[
                            n.estimated_coverage_nok && `${T("Dekningssum")}: ${fmtNok(n.estimated_coverage_nok)}`,
                            n.estimated_annual_premium_nok && `${T("Premie")}: ${fmtRange(n.estimated_annual_premium_nok)} ${T("/år")}`,
                          ].filter(Boolean).join(" · ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* AI narrative + risk offer */}
      <div className="broker-card">
        <button onClick={() => setNarrativeOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-foreground">
          <span className="flex items-center gap-1.5"><Sparkles className="w-4 h-4" /> {T("AI-risikoanalyse")}</span>
          {narrativeOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {narrativeOpen && (
          <div className="mt-3 space-y-3">
            <div className="flex gap-2 flex-wrap">
              <button onClick={handleGenerateNarrative} disabled={genLoading}
                className="px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1">
                {genLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                {T("Generer risikonarrativ")}
              </button>
              <button onClick={handleGenerateOffer} disabled={genLoading}
                className="px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1">
                {genLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />}
                {T("Generer forsikringstilbud")}
              </button>
            </div>
            {genErr && <p className="text-xs text-red-600">{genErr}</p>}

            {narrative && (
              <div className="bg-muted rounded-lg p-3">
                <p className="text-xs font-semibold text-foreground mb-1">{T("Risikonarrativ")}</p>
                <p className="text-xs text-foreground whitespace-pre-wrap">{narrative}</p>
              </div>
            )}

            {riskOffer && (
              <div className="bg-muted rounded-lg p-3 space-y-2">
                <p className="text-xs font-semibold text-foreground">{T("Forsikringstilbud")}</p>
                {riskOffer.sammendrag && (
                  <p className="text-xs text-foreground whitespace-pre-wrap">{riskOffer.sammendrag}</p>
                )}
                {riskOffer.total_premieanslag && (
                  <p className="text-xs text-primary font-medium">
                    {T("Totalt premieanslag")}: {riskOffer.total_premieanslag}
                  </p>
                )}
                {riskOffer.anbefalinger && riskOffer.anbefalinger.length > 0 && (
                  <ul className="space-y-1">
                    {riskOffer.anbefalinger.map((a, i) => (
                      <li key={i} className="text-xs text-foreground">
                        • <strong>{a.type ?? ""}</strong>{a.begrunnelse ? `: ${a.begrunnelse}` : ""}
                        {a.estimert_premie && ` — ${a.estimert_premie}`}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Offer upload */}
      <div className="broker-card">
        <button onClick={() => setUploadOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-foreground">
          <span className="flex items-center gap-1.5"><Upload className="w-4 h-4" /> {T("Last opp tilbud (PDF)")}</span>
          {uploadOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {uploadOpen && (
          <div className="mt-3 space-y-3">
            <p className="text-xs text-muted-foreground">
              {T("Last opp én eller flere PDF-filer med forsikringstilbud. AI-agenten analyserer dem i bakgrunnen.")}
            </p>
            <input
              type="file" accept=".pdf" multiple
              onChange={(e) => setUploadFiles(e.target.files)}
              className="block w-full text-xs text-muted-foreground file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-primary file:text-white hover:file:bg-primary/90 cursor-pointer"
            />
            {uploadFiles && uploadFiles.length > 0 && (
              <p className="text-xs text-muted-foreground">{uploadFiles.length} {T("fil(er) valgt")}</p>
            )}
            {uploadErr && <p className="text-xs text-red-600">{uploadErr}</p>}
            <div className="flex gap-2">
              <button onClick={handleUpload} disabled={uploading || !uploadFiles?.length}
                className="px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1">
                {uploading && <Loader2 className="w-3 h-3 animate-spin" />}
                {uploading ? T("Laster opp…") : T("Last opp")}
              </button>
              <button type="button" onClick={() => setUploadOpen(false)}
                className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground">{T("Avbryt")}</button>
            </div>
          </div>
        )}
      </div>

      {/* Uploaded offers */}
      <div className="broker-card">
        <button onClick={() => setOffersOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-foreground">
          <span>📎 {T("Innhentede tilbud")} {offers.length > 0 && `(${offers.length})`}</span>
          {offersOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {offersOpen && (
          <div className="mt-3">
            {offers.length === 0 ? (
              <p className="text-xs text-muted-foreground">{T("Ingen tilbud lastet opp.")}</p>
            ) : (
              <div className="divide-y divide-border">
                {offers.map((o) => (
                  <div key={o.id} className="py-2.5 flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-foreground">{o.insurer_name}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{o.filename} · {o.uploaded_at.slice(0, 10)}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <select
                        value={o.status ?? "pending"}
                        onChange={(e) => handleStatusChange(o.id, e.target.value)}
                        className="text-xs border border-border rounded px-1.5 py-1 bg-card focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {Object.entries(OFFER_STATUS_LABEL).map(([v, l]) => (
                          <option key={v} value={v}>{l}</option>
                        ))}
                      </select>
                      <button onClick={() => handleDeleteOffer(o.id)} className="text-muted-foreground hover:text-red-500">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
