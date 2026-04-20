"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getInsuranceDocuments, uploadInsuranceDocument, deleteInsuranceDocument,
  compareInsuranceDocuments, chatWithInsuranceDocument,
  downloadInsuranceDocumentPdf, getDocumentKeyPoints, getSimilarDocuments,
  type InsuranceDocument,
  type DocumentCompareOut,
} from "@/lib/api";
import { Loader2, Upload, Trash2, Download, MessageSquare, Sparkles, FileText, Link2, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { fmtDate } from "@/lib/format";
import { OfferComparisonTable } from "@/components/offers/OfferComparisonTable";
import { useT } from "@/lib/i18n";

const KEYPOINT_LABELS: Record<string, string> = {
  om_dokumentet: "Om dokumentet",
  sammendrag: "Sammendrag",
  hva_dekkes: "Hva dekkes",
  viktige_vilkår: "Viktige vilkår",
  unntak: "Unntak",
  egenandel: "Egenandel",
  periode: "Periode",
  kontakt: "Kontakt",
};

export default function DocumentsPanel() {
  const T = useT();
  const [orgnrFilter, setOrgnrFilter]     = useState("");
  const [appliedFilter, setAppliedFilter] = useState<string | undefined>(undefined);

  const [uploadOpen, setUploadOpen]   = useState(false);
  const [uploadFile, setUploadFile]   = useState<File | null>(null);
  const [uploadOrgnr, setUploadOrgnr] = useState("");
  const [uploadTags, setUploadTags]   = useState("");
  const [uploading, setUploading]     = useState(false);
  const [uploadErr, setUploadErr]     = useState<string | null>(null);

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [comparing, setComparing]     = useState(false);
  const [compareResult, setCompareResult] = useState<DocumentCompareOut | null>(null);
  const [compareErr, setCompareErr]   = useState<string | null>(null);

  const [chatDocId, setChatDocId]       = useState<number | null>(null);
  const [chatDocName, setChatDocName]   = useState("");
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatAnswer, setChatAnswer]     = useState<string | null>(null);
  const [chatLoading, setChatLoading]   = useState(false);

  // Key points
  const [keypointsDocId, setKeypointsDocId] = useState<number | null>(null);
  const [keypoints, setKeypoints]           = useState<Record<string, unknown> | null>(null);
  const [keypointsLoading, setKeypointsLoading] = useState(false);

  // PDF viewer
  const [pdfViewDocId, setPdfViewDocId] = useState<number | null>(null);
  const [pdfViewUrl, setPdfViewUrl]     = useState<string | null>(null);
  const [pdfLoading, setPdfLoading]     = useState(false);

  // Similar docs
  const [similarDocId, setSimilarDocId] = useState<number | null>(null);
  const { data: similarDocs } = useSWR<InsuranceDocument[]>(
    similarDocId ? `similar-${similarDocId}` : null,
    () => getSimilarDocuments(similarDocId!),
  );

  const { data: documents, isLoading, mutate } = useSWR<InsuranceDocument[]>(
    ["insurance-documents", appliedFilter],
    () => getInsuranceDocuments(appliedFilter),
  );

  async function handleUpload() {
    if (!uploadFile) return;
    setUploading(true); setUploadErr(null);
    try {
      await uploadInsuranceDocument(uploadFile, { orgnr: uploadOrgnr || undefined, tags: uploadTags || undefined });
      setUploadFile(null); setUploadOrgnr(""); setUploadTags("");
      setUploadOpen(false); mutate();
    } catch (e) { setUploadErr(String(e)); }
    finally { setUploading(false); }
  }

  async function handleDelete(id: number) {
    await deleteInsuranceDocument(id);
    setSelectedIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
    if (chatDocId === id) setChatDocId(null);
    if (keypointsDocId === id) setKeypointsDocId(null);
    if (pdfViewDocId === id) { setPdfViewDocId(null); setPdfViewUrl(null); }
    mutate();
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const n = new Set(prev);
      if (n.has(id)) { n.delete(id); } else if (n.size < 2) { n.add(id); }
      return n;
    });
    setCompareResult(null);
  }

  async function handleCompare() {
    const ids = Array.from(selectedIds) as [number, number];
    setComparing(true); setCompareErr(null); setCompareResult(null);
    try {
      const r = await compareInsuranceDocuments(ids);
      setCompareResult(r);
    } catch (e) { setCompareErr(String(e)); }
    finally { setComparing(false); }
  }

  async function handleChat() {
    if (!chatDocId || !chatQuestion.trim()) return;
    setChatLoading(true); setChatAnswer(null);
    try {
      const r = await chatWithInsuranceDocument(chatDocId, chatQuestion, appliedFilter);
      setChatAnswer(r.answer);
    } catch (e) { setChatAnswer(`${T("Feil")}: ${String(e)}`); }
    finally { setChatLoading(false); }
  }

  async function handleKeypoints(doc: InsuranceDocument) {
    if (keypointsDocId === doc.id) { setKeypointsDocId(null); setKeypoints(null); return; }
    setKeypointsDocId(doc.id); setKeypoints(null);
    setKeypointsLoading(true);
    try {
      const kp = await getDocumentKeyPoints(doc.id);
      setKeypoints(kp);
    } catch { setKeypoints({}); }
    finally { setKeypointsLoading(false); }
  }

  async function handleViewPdf(doc: InsuranceDocument) {
    if (pdfViewDocId === doc.id) {
      if (pdfViewUrl) URL.revokeObjectURL(pdfViewUrl);
      setPdfViewDocId(null); setPdfViewUrl(null); return;
    }
    if (pdfViewUrl) URL.revokeObjectURL(pdfViewUrl);
    setPdfViewDocId(doc.id); setPdfViewUrl(null);
    setPdfLoading(true);
    try {
      const res = await fetch(`/bapi/insurance-documents/${doc.id}/pdf`);
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      setPdfViewUrl(URL.createObjectURL(blob));
    } catch { setPdfViewUrl(null); }
    finally { setPdfLoading(false); }
  }

  function openChat(doc: InsuranceDocument) {
    setChatDocId(doc.id); setChatDocName(doc.filename); setChatQuestion(""); setChatAnswer(null);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{T("Dokumenter")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{T("Forsikringsdokumenter og tilbud lastet opp for kundene")}</p>
        </div>
        <button onClick={() => setUploadOpen((o) => !o)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 flex-shrink-0">
          <Upload className="w-4 h-4" /> {T("Last opp")}
        </button>
      </div>

      {/* Upload panel */}
      {uploadOpen && (
        <div className="broker-card space-y-3">
          <p className="text-sm font-semibold text-foreground">{T("Last opp dokument")}</p>
          <div>
            <label className="label-xs" htmlFor="doc-upload-file">{T("PDF-fil *")}</label>
            <input id="doc-upload-file" type="file" accept=".pdf"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
              className="block w-full text-xs text-muted-foreground file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-primary file:text-white hover:file:bg-primary/90 cursor-pointer mt-0.5" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label-xs" htmlFor="doc-upload-orgnr">{T("Org.nr (valgfritt)")}</label>
              <input id="doc-upload-orgnr" type="text" value={uploadOrgnr} onChange={(e) => setUploadOrgnr(e.target.value)}
                placeholder="984851006" className="input-sm" />
            </div>
            <div>
              <label className="label-xs" htmlFor="doc-upload-tags">{T("Tagger (kommaseparert)")}</label>
              <input id="doc-upload-tags" type="text" value={uploadTags} onChange={(e) => setUploadTags(e.target.value)}
                placeholder={T("tilbud, ansvar")} className="input-sm" />
            </div>
          </div>
          {uploadErr && <p className="text-xs text-red-600">{uploadErr}</p>}
          <div className="flex gap-2">
            <button onClick={handleUpload} disabled={uploading || !uploadFile}
              className="px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1">
              {uploading && <Loader2 className="w-3 h-3 animate-spin" />}
              {uploading ? T("Laster opp…") : T("Last opp")}
            </button>
            <button type="button" onClick={() => setUploadOpen(false)}
              className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground">{T("Avbryt")}</button>
          </div>
        </div>
      )}

      {/* Filter + compare bar */}
      <div className="broker-card space-y-3">
        <div className="flex gap-2">
          <input type="text" value={orgnrFilter} onChange={(e) => setOrgnrFilter(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && setAppliedFilter(orgnrFilter.trim() || undefined)}
            placeholder={T("Filtrer på org.nr")}
            className="flex-1 px-3 py-2 text-sm border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary" />
          <button onClick={() => setAppliedFilter(orgnrFilter.trim() || undefined)}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90">{T("Søk")}</button>
          {appliedFilter && (
            <button onClick={() => { setOrgnrFilter(""); setAppliedFilter(undefined); }}
              className="px-4 py-2 rounded-lg bg-muted text-muted-foreground text-sm font-medium hover:bg-muted">{T("Nullstill")}</button>
          )}
        </div>

        {selectedIds.size === 2 && (
          <div className="flex items-center gap-3">
            <button onClick={handleCompare} disabled={comparing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
              {comparing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              {T("AI-sammenlign valgte (2)")}
            </button>
            <button onClick={() => { setSelectedIds(new Set()); setCompareResult(null); }}
              className="text-xs text-muted-foreground hover:text-foreground">{T("Fjern valg")}</button>
          </div>
        )}
        {selectedIds.size === 1 && <p className="text-xs text-muted-foreground">{T("Velg ett dokument til for å sammenligne")}</p>}
      </div>

      {/* Compare result */}
      {(compareResult || compareErr) && (
        <div className="broker-card">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-primary" /> {T("AI-sammenligning")}
            </p>
            <button onClick={() => setCompareResult(null)} className="text-xs text-muted-foreground hover:text-foreground">{T("Lukk")}</button>
          </div>
          {compareErr && <p className="text-xs text-red-600">{compareErr}</p>}
          {compareResult && <OfferComparisonTable result={compareResult} />}
        </div>
      )}

      {/* Inline chat panel */}
      {chatDocId != null && (
        <div className="broker-card space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <MessageSquare className="w-4 h-4 text-primary" /> {T("Chat")} — {chatDocName}
            </p>
            <button onClick={() => { setChatDocId(null); setChatAnswer(null); }}
              className="text-xs text-muted-foreground hover:text-foreground">{T("Lukk")}</button>
          </div>
          <div className="flex gap-2">
            <input type="text" value={chatQuestion} onChange={(e) => setChatQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleChat()}
              placeholder={T("Still et spørsmål om dokumentet…")}
              className="flex-1 px-3 py-2 text-sm border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary" />
            <button onClick={handleChat} disabled={chatLoading || !chatQuestion.trim()}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1">
              {chatLoading && <Loader2 className="w-4 h-4 animate-spin" />} {T("Send")}
            </button>
          </div>
          {chatAnswer && <div className="bg-muted rounded-lg p-3"><p className="text-xs text-foreground whitespace-pre-wrap">{chatAnswer}</p></div>}
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="broker-card space-y-3">
          {[...Array(5)].map((_, i) => <div key={i} className="h-8 rounded animate-pulse bg-muted" />)}
        </div>
      )}

      {/* Document list */}
      {!isLoading && documents && documents.length > 0 && (
        <div className="space-y-2">
          {documents.map((doc) => (
            <div key={doc.id} className={`broker-card transition-colors ${selectedIds.has(doc.id) ? "ring-1 ring-ring" : ""}`}>
              {/* Document row */}
              <div className="flex items-start gap-3">
                <input type="checkbox" checked={selectedIds.has(doc.id)} onChange={() => toggleSelect(doc.id)}
                  disabled={!selectedIds.has(doc.id) && selectedIds.size >= 2}
                  className="mt-1 rounded border-border cursor-pointer accent-primary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">{doc.filename}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {doc.orgnr && <Link href={`/search/${doc.orgnr}`} className="hover:underline text-primary">{doc.orgnr}</Link>}
                        {doc.orgnr && " · "}
                        {fmtDate(doc.created_at)}
                      </p>
                      {doc.tags && doc.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {doc.tags.map((tag) => (
                            <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">{tag}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button onClick={() => handleKeypoints(doc)} title={T("Nøkkelpunkter")}
                        className={`p-1.5 rounded hover:bg-muted ${keypointsDocId === doc.id ? "text-primary" : "text-muted-foreground"}`}>
                        <FileText className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleViewPdf(doc)} title={T("Vis PDF")}
                        className={`p-1.5 rounded hover:bg-muted ${pdfViewDocId === doc.id ? "text-primary" : "text-muted-foreground"}`}>
                        {pdfViewDocId === doc.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                      <button onClick={() => setSimilarDocId(similarDocId === doc.id ? null : doc.id)}
                        title={T("Lignende dokumenter")}
                        className={`p-1.5 rounded hover:bg-muted ${similarDocId === doc.id ? "text-primary" : "text-muted-foreground"}`}>
                        <Link2 className="w-4 h-4" />
                      </button>
                      <button onClick={() => openChat(doc)} title={T("Chat med dokument")}
                        className={`p-1.5 rounded hover:bg-muted ${chatDocId === doc.id ? "text-primary" : "text-muted-foreground"}`}>
                        <MessageSquare className="w-4 h-4" />
                      </button>
                      <button onClick={() => downloadInsuranceDocumentPdf(doc.id, doc.filename)} title={T("Last ned PDF")}
                        className="p-1.5 rounded text-muted-foreground hover:bg-muted hover:text-foreground">
                        <Download className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleDelete(doc.id)} title={T("Slett")}
                        className="p-1.5 rounded text-muted-foreground hover:bg-muted hover:text-red-500">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Key points panel */}
              {keypointsDocId === doc.id && (
                <div className="mt-3 pt-3 border-t border-border">
                  {keypointsLoading ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="w-4 h-4 animate-spin" /> {T("Henter nøkkelpunkter…")}
                    </div>
                  ) : keypoints && Object.keys(keypoints).length > 0 ? (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-foreground">{T("Nøkkelpunkter")}</p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {Object.entries(keypoints)
                          .filter(([k]) => k !== "doc_id" && k !== "title")
                          .map(([k, v]) => v ? (
                            <div key={k} className="bg-muted rounded-lg p-2">
                              <p className="text-xs font-medium text-primary mb-0.5">
                                {T(KEYPOINT_LABELS[k] ?? k)}
                              </p>
                              <p className="text-xs text-foreground whitespace-pre-wrap">{String(v)}</p>
                            </div>
                          ) : null)}
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">{T("Ingen nøkkelpunkter tilgjengelig.")}</p>
                  )}
                </div>
              )}

              {/* PDF viewer */}
              {pdfViewDocId === doc.id && (
                <div className="mt-3 pt-3 border-t border-border">
                  {pdfLoading ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="w-4 h-4 animate-spin" /> {T("Laster PDF…")}
                    </div>
                  ) : pdfViewUrl ? (
                    <iframe src={pdfViewUrl} className="w-full rounded-lg border border-border" style={{ height: "500px" }} />
                  ) : (
                    <p className="text-xs text-muted-foreground">{T("Kunne ikke laste PDF.")}</p>
                  )}
                </div>
              )}

              {/* Similar documents */}
              {similarDocId === doc.id && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-xs font-semibold text-foreground mb-2">{T("Lignende dokumenter")}</p>
                  {!similarDocs ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="w-4 h-4 animate-spin" /> {T("Søker…")}
                    </div>
                  ) : similarDocs.length === 0 ? (
                    <p className="text-xs text-muted-foreground">{T("Ingen lignende dokumenter funnet.")}</p>
                  ) : (
                    <div className="space-y-1">
                      {similarDocs.map((s) => (
                        <div key={s.id} className="flex items-center justify-between text-xs py-1 border-b border-border">
                          <span className="text-foreground">{s.filename}</span>
                          <div className="flex items-center gap-2">
                            {s.orgnr && <Link href={`/search/${s.orgnr}`} className="text-primary hover:underline">{s.orgnr}</Link>}
                            <button onClick={() => downloadInsuranceDocumentPdf(s.id, s.filename)}
                              className="text-muted-foreground hover:text-foreground">
                              <Download className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          <p className="text-xs text-muted-foreground pl-1">{documents.length} {T("dokument(er)")}</p>
        </div>
      )}

      {!isLoading && documents && documents.length === 0 && (
        <div className="broker-card text-center py-12">
          <p className="text-sm font-medium text-foreground">{T("Ingen dokumenter funnet")}</p>
          <p className="text-xs text-muted-foreground mt-1">
            {appliedFilter ? `${T("Ingen dokumenter for org.nr")} ${appliedFilter}.` : T("Last opp dokumenter via knappen øverst til høyre.")}
          </p>
        </div>
      )}

      {!isLoading && !documents && (
        <div className="broker-card text-center py-12">
          <p className="text-sm text-muted-foreground">{T("Kunne ikke laste dokumenter.")}</p>
        </div>
      )}
    </div>
  );
}
