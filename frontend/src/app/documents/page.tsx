"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getInsuranceDocuments, uploadInsuranceDocument, deleteInsuranceDocument,
  compareInsuranceDocuments, chatWithInsuranceDocument,
  downloadInsuranceDocumentPdf, getDocumentKeyPoints, getSimilarDocuments,
  type InsuranceDocument,
} from "@/lib/api";
import { Loader2, Upload, Trash2, Download, MessageSquare, Sparkles, FileText, Link2, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { fmtDate } from "@/lib/format";

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

export default function DocumentsPage() {
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
  const [compareResult, setCompareResult] = useState<string | null>(null);
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
      setCompareResult(r.comparison);
    } catch (e) { setCompareErr(String(e)); }
    finally { setComparing(false); }
  }

  async function handleChat() {
    if (!chatDocId || !chatQuestion.trim()) return;
    setChatLoading(true); setChatAnswer(null);
    try {
      const r = await chatWithInsuranceDocument(chatDocId, chatQuestion, appliedFilter);
      setChatAnswer(r.answer);
    } catch (e) { setChatAnswer(`Feil: ${String(e)}`); }
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
          <h1 className="text-2xl font-bold text-[#2C3E50]">Dokumenter</h1>
          <p className="text-sm text-[#8A7F74] mt-1">Forsikringsdokumenter og tilbud lastet opp for kundene</p>
        </div>
        <button onClick={() => setUploadOpen((o) => !o)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166] flex-shrink-0">
          <Upload className="w-4 h-4" /> Last opp
        </button>
      </div>

      {/* Upload panel */}
      {uploadOpen && (
        <div className="broker-card space-y-3">
          <p className="text-sm font-semibold text-[#2C3E50]">Last opp dokument</p>
          <div>
            <label className="label-xs">PDF-fil *</label>
            <input type="file" accept=".pdf"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
              className="block w-full text-xs text-[#8A7F74] file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-[#2C3E50] file:text-white hover:file:bg-[#3d5166] cursor-pointer mt-0.5" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label-xs">Org.nr (valgfritt)</label>
              <input type="text" value={uploadOrgnr} onChange={(e) => setUploadOrgnr(e.target.value)}
                placeholder="984851006" className="input-sm" />
            </div>
            <div>
              <label className="label-xs">Tagger (kommaseparert)</label>
              <input type="text" value={uploadTags} onChange={(e) => setUploadTags(e.target.value)}
                placeholder="tilbud, ansvar" className="input-sm" />
            </div>
          </div>
          {uploadErr && <p className="text-xs text-red-600">{uploadErr}</p>}
          <div className="flex gap-2">
            <button onClick={handleUpload} disabled={uploading || !uploadFile}
              className="px-3 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1">
              {uploading && <Loader2 className="w-3 h-3 animate-spin" />}
              {uploading ? "Laster opp…" : "Last opp"}
            </button>
            <button type="button" onClick={() => setUploadOpen(false)}
              className="px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#8A7F74]">Avbryt</button>
          </div>
        </div>
      )}

      {/* Filter + compare bar */}
      <div className="broker-card space-y-3">
        <div className="flex gap-2">
          <input type="text" value={orgnrFilter} onChange={(e) => setOrgnrFilter(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && setAppliedFilter(orgnrFilter.trim() || undefined)}
            placeholder="Filtrer på org.nr"
            className="flex-1 px-3 py-2 text-sm border border-[#EDE8E3] rounded-lg text-[#2C3E50] placeholder-[#C8BEB4] focus:outline-none focus:border-[#2C3E50]" />
          <button onClick={() => setAppliedFilter(orgnrFilter.trim() || undefined)}
            className="px-4 py-2 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166]">Søk</button>
          {appliedFilter && (
            <button onClick={() => { setOrgnrFilter(""); setAppliedFilter(undefined); }}
              className="px-4 py-2 rounded-lg bg-[#EDE8E3] text-[#8A7F74] text-sm font-medium hover:bg-[#DDD8D3]">Nullstill</button>
          )}
        </div>

        {selectedIds.size === 2 && (
          <div className="flex items-center gap-3">
            <button onClick={handleCompare} disabled={comparing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50">
              {comparing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              AI-sammenlign valgte (2)
            </button>
            <button onClick={() => { setSelectedIds(new Set()); setCompareResult(null); }}
              className="text-xs text-[#8A7F74] hover:text-[#2C3E50]">Fjern valg</button>
          </div>
        )}
        {selectedIds.size === 1 && <p className="text-xs text-[#8A7F74]">Velg ett dokument til for å sammenligne</p>}
      </div>

      {/* Compare result */}
      {(compareResult || compareErr) && (
        <div className="broker-card">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-[#4A6FA5]" /> AI-sammenligning
            </p>
            <button onClick={() => setCompareResult(null)} className="text-xs text-[#8A7F74] hover:text-[#2C3E50]">Lukk</button>
          </div>
          {compareErr && <p className="text-xs text-red-600">{compareErr}</p>}
          {compareResult && <div className="bg-[#F9F7F4] rounded-lg p-3"><p className="text-xs text-[#2C3E50] whitespace-pre-wrap">{compareResult}</p></div>}
        </div>
      )}

      {/* Inline chat panel */}
      {chatDocId != null && (
        <div className="broker-card space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
              <MessageSquare className="w-4 h-4 text-[#4A6FA5]" /> Chat — {chatDocName}
            </p>
            <button onClick={() => { setChatDocId(null); setChatAnswer(null); }}
              className="text-xs text-[#8A7F74] hover:text-[#2C3E50]">Lukk</button>
          </div>
          <div className="flex gap-2">
            <input type="text" value={chatQuestion} onChange={(e) => setChatQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleChat()}
              placeholder="Still et spørsmål om dokumentet…"
              className="flex-1 px-3 py-2 text-sm border border-[#EDE8E3] rounded-lg text-[#2C3E50] placeholder-[#C8BEB4] focus:outline-none focus:border-[#2C3E50]" />
            <button onClick={handleChat} disabled={chatLoading || !chatQuestion.trim()}
              className="px-4 py-2 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1">
              {chatLoading && <Loader2 className="w-4 h-4 animate-spin" />} Send
            </button>
          </div>
          {chatAnswer && <div className="bg-[#F9F7F4] rounded-lg p-3"><p className="text-xs text-[#2C3E50] whitespace-pre-wrap">{chatAnswer}</p></div>}
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="broker-card space-y-3">
          {[...Array(5)].map((_, i) => <div key={i} className="h-8 rounded animate-pulse bg-[#EDE8E3]" />)}
        </div>
      )}

      {/* Document list */}
      {!isLoading && documents && documents.length > 0 && (
        <div className="space-y-2">
          {documents.map((doc) => (
            <div key={doc.id} className={`broker-card transition-colors ${selectedIds.has(doc.id) ? "ring-1 ring-[#4A6FA5]" : ""}`}>
              {/* Document row */}
              <div className="flex items-start gap-3">
                <input type="checkbox" checked={selectedIds.has(doc.id)} onChange={() => toggleSelect(doc.id)}
                  disabled={!selectedIds.has(doc.id) && selectedIds.size >= 2}
                  className="mt-1 rounded border-[#D4C9B8] cursor-pointer accent-[#4A6FA5] flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[#2C3E50] truncate">{doc.filename}</p>
                      <p className="text-xs text-[#8A7F74] mt-0.5">
                        {doc.orgnr && <Link href={`/search/${doc.orgnr}`} className="hover:underline text-[#4A6FA5]">{doc.orgnr}</Link>}
                        {doc.orgnr && " · "}
                        {fmtDate(doc.created_at)}
                      </p>
                      {doc.tags && doc.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {doc.tags.map((tag) => (
                            <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-[#EDE8E3] text-[#8A7F74]">{tag}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button onClick={() => handleKeypoints(doc)} title="Nøkkelpunkter"
                        className={`p-1.5 rounded hover:bg-[#EDE8E3] ${keypointsDocId === doc.id ? "text-[#4A6FA5]" : "text-[#C4BDB4]"}`}>
                        <FileText className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleViewPdf(doc)} title="Vis PDF"
                        className={`p-1.5 rounded hover:bg-[#EDE8E3] ${pdfViewDocId === doc.id ? "text-[#4A6FA5]" : "text-[#C4BDB4]"}`}>
                        {pdfViewDocId === doc.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                      <button onClick={() => setSimilarDocId(similarDocId === doc.id ? null : doc.id)}
                        title="Lignende dokumenter"
                        className={`p-1.5 rounded hover:bg-[#EDE8E3] ${similarDocId === doc.id ? "text-[#4A6FA5]" : "text-[#C4BDB4]"}`}>
                        <Link2 className="w-4 h-4" />
                      </button>
                      <button onClick={() => openChat(doc)} title="Chat med dokument"
                        className={`p-1.5 rounded hover:bg-[#EDE8E3] ${chatDocId === doc.id ? "text-[#4A6FA5]" : "text-[#C4BDB4]"}`}>
                        <MessageSquare className="w-4 h-4" />
                      </button>
                      <button onClick={() => downloadInsuranceDocumentPdf(doc.id, doc.filename)} title="Last ned PDF"
                        className="p-1.5 rounded text-[#C4BDB4] hover:bg-[#EDE8E3] hover:text-[#2C3E50]">
                        <Download className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleDelete(doc.id)} title="Slett"
                        className="p-1.5 rounded text-[#C4BDB4] hover:bg-[#EDE8E3] hover:text-red-500">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Key points panel */}
              {keypointsDocId === doc.id && (
                <div className="mt-3 pt-3 border-t border-[#EDE8E3]">
                  {keypointsLoading ? (
                    <div className="flex items-center gap-2 text-xs text-[#8A7F74]">
                      <Loader2 className="w-4 h-4 animate-spin" /> Henter nøkkelpunkter…
                    </div>
                  ) : keypoints && Object.keys(keypoints).length > 0 ? (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-[#2C3E50]">Nøkkelpunkter</p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {Object.entries(keypoints)
                          .filter(([k]) => k !== "doc_id" && k !== "title")
                          .map(([k, v]) => v ? (
                            <div key={k} className="bg-[#F9F7F4] rounded-lg p-2">
                              <p className="text-xs font-medium text-[#4A6FA5] mb-0.5">
                                {KEYPOINT_LABELS[k] ?? k}
                              </p>
                              <p className="text-xs text-[#2C3E50] whitespace-pre-wrap">{String(v)}</p>
                            </div>
                          ) : null)}
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-[#8A7F74]">Ingen nøkkelpunkter tilgjengelig.</p>
                  )}
                </div>
              )}

              {/* PDF viewer */}
              {pdfViewDocId === doc.id && (
                <div className="mt-3 pt-3 border-t border-[#EDE8E3]">
                  {pdfLoading ? (
                    <div className="flex items-center gap-2 text-xs text-[#8A7F74]">
                      <Loader2 className="w-4 h-4 animate-spin" /> Laster PDF…
                    </div>
                  ) : pdfViewUrl ? (
                    <iframe src={pdfViewUrl} className="w-full rounded-lg border border-[#EDE8E3]" style={{ height: "500px" }} />
                  ) : (
                    <p className="text-xs text-[#8A7F74]">Kunne ikke laste PDF.</p>
                  )}
                </div>
              )}

              {/* Similar documents */}
              {similarDocId === doc.id && (
                <div className="mt-3 pt-3 border-t border-[#EDE8E3]">
                  <p className="text-xs font-semibold text-[#2C3E50] mb-2">Lignende dokumenter</p>
                  {!similarDocs ? (
                    <div className="flex items-center gap-2 text-xs text-[#8A7F74]">
                      <Loader2 className="w-4 h-4 animate-spin" /> Søker…
                    </div>
                  ) : similarDocs.length === 0 ? (
                    <p className="text-xs text-[#8A7F74]">Ingen lignende dokumenter funnet.</p>
                  ) : (
                    <div className="space-y-1">
                      {similarDocs.map((s) => (
                        <div key={s.id} className="flex items-center justify-between text-xs py-1 border-b border-[#EDE8E3]">
                          <span className="text-[#2C3E50]">{s.filename}</span>
                          <div className="flex items-center gap-2">
                            {s.orgnr && <Link href={`/search/${s.orgnr}`} className="text-[#4A6FA5] hover:underline">{s.orgnr}</Link>}
                            <button onClick={() => downloadInsuranceDocumentPdf(s.id, s.filename)}
                              className="text-[#C4BDB4] hover:text-[#2C3E50]">
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
          <p className="text-xs text-[#8A7F74] pl-1">{documents.length} dokument(er)</p>
        </div>
      )}

      {!isLoading && documents && documents.length === 0 && (
        <div className="broker-card text-center py-12">
          <p className="text-sm font-medium text-[#2C3E50]">Ingen dokumenter funnet</p>
          <p className="text-xs text-[#8A7F74] mt-1">
            {appliedFilter ? `Ingen dokumenter for org.nr ${appliedFilter}.` : "Last opp dokumenter via knappen øverst til høyre."}
          </p>
        </div>
      )}

      {!isLoading && !documents && (
        <div className="broker-card text-center py-12">
          <p className="text-sm text-[#8A7F74]">Kunne ikke laste dokumenter.</p>
        </div>
      )}
    </div>
  );
}
