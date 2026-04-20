"use client";

import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import useSWR from "swr";
import {
  getTender,
  sendTender,
  remindTender,
  uploadTenderOffer,
  analyseTender,
  updateTender,
  downloadTenderPresentationPdf,
  type Tender,
} from "@/lib/api";
import {
  ArrowLeft,
  Send,
  BarChart2,
  Bell,
  Clock,
  CheckCircle,
  FileText,
  FileDown,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { useT } from "@/lib/i18n";

const STATUS_BADGE: Record<string, { labelKey: string; cls: string; icon: typeof Clock }> = {
  draft: { labelKey: "Utkast", cls: "bg-gray-100 text-gray-700", icon: FileText },
  sent: { labelKey: "Sendt", cls: "bg-blue-50 text-blue-700", icon: Send },
  closed: { labelKey: "Lukket", cls: "bg-yellow-50 text-yellow-700", icon: Clock },
  analysed: { labelKey: "Analysert", cls: "bg-green-50 text-green-700", icon: BarChart2 },
};

const RECIPIENT_STATUS: Record<string, { labelKey: string; cls: string }> = {
  pending: { labelKey: "Venter", cls: "text-gray-500" },
  sent: { labelKey: "Sendt", cls: "text-blue-600" },
  received: { labelKey: "Svar mottatt", cls: "text-green-600" },
  declined: { labelKey: "Avslått", cls: "text-red-500" },
};

export default function TenderDetailPage() {
  const T = useT();
  const { id } = useParams<{ id: string }>();
  const { data: tender, mutate } = useSWR<Tender>(`tender-${id}`, () => getTender(Number(id)));
  const [sending, setSending] = useState(false);
  const [reminding, setReminding] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadInsurer, setUploadInsurer] = useState("");

  if (!tender) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  const s = STATUS_BADGE[tender.status] || STATUS_BADGE.draft;
  const StatusIcon = s.icon;

  async function handleSend() {
    setSending(true);
    try {
      await sendTender(Number(id));
      mutate();
    } catch {
      toast.error(T("Kunne ikke sende anbudsforespørsler"));
    } finally {
      setSending(false);
    }
  }

  async function handleRemind() {
    setReminding(true);
    try {
      const res = await remindTender(Number(id));
      if (res.reminders_sent > 0) {
        toast.success(
          `${T("Purring sendt til")} ${res.reminders_sent} ${T("selskap(er)")}`,
        );
      } else {
        toast.message(T("Ingen ventende mottakere å purre"));
      }
      mutate();
    } catch {
      toast.error(T("Kunne ikke sende purring"));
    } finally {
      setReminding(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !uploadInsurer) return;
    setUploading(true);
    try {
      const recipient = tender?.recipients.find((r) => r.insurer_name === uploadInsurer);
      await uploadTenderOffer(Number(id), file, uploadInsurer, recipient?.id);
      setUploadInsurer("");
      mutate();
    } catch {
      toast.error(T("Kunne ikke laste opp tilbud"));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleAnalyse() {
    setAnalysing(true);
    try {
      await analyseTender(Number(id));
      mutate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : T("Analyse feilet"));
    } finally {
      setAnalysing(false);
    }
  }

  async function handleClose() {
    await updateTender(Number(id), { status: "closed" });
    mutate();
  }

  // Type the analysis result for safe rendering
  interface AnalysisField {
    felt: string;
    verdier?: Record<string, string>;
    kommentar?: string;
    konfidens?: string;
  }
  interface AnalysisCategory {
    kategori: string;
    felter?: AnalysisField[];
  }
  interface AnalysisResult {
    anbefaling?: { forsikringsgiver: string; begrunnelse: string };
    oppsummering?: string;
    nøkkelforskjeller?: string[];
    sammenligning?: AnalysisCategory[];
  }
  const analysis = tender.analysis_result as AnalysisResult | undefined;

  return (
    <div>
      {/* Header */}
      <Link href="/tenders" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="w-4 h-4" />
        {T("Tilbake til anbud")}
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-foreground">{tender.title}</h1>
            <span className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium ${s.cls}`}>
              <StatusIcon className="w-3 h-3" />
              {T(s.labelKey)}
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {tender.product_types.join(", ")}
            {tender.deadline && ` · ${T("Frist")}: ${tender.deadline}`}
          </p>
        </div>
        <div className="flex gap-2">
          {tender.status === "draft" && (
            <button
              onClick={handleSend}
              disabled={sending || tender.recipients.length === 0}
              className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/90 disabled:opacity-50"
            >
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              {T("Send til selskaper")}
            </button>
          )}
          {tender.status === "sent" && (
            <>
              <button
                onClick={handleRemind}
                disabled={reminding}
                className="flex items-center gap-1.5 px-4 py-2 border border-border text-foreground text-sm rounded-lg hover:bg-muted disabled:opacity-50"
                title={T("Send purring til mottakere som ikke har svart")}
              >
                {reminding ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Bell className="w-4 h-4" />
                )}
                {T("Send purring")}
              </button>
              <button
                onClick={handleClose}
                className="flex items-center gap-1.5 px-4 py-2 bg-brand-warning text-white text-sm rounded-lg hover:bg-brand-warning/90"
              >
                <Clock className="w-4 h-4" />
                {T("Lukk anbud")}
              </button>
            </>
          )}
          {tender.offers.length >= 2 && tender.status !== "draft" && (
            <button
              onClick={handleAnalyse}
              disabled={analysing}
              className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80 disabled:opacity-50"
            >
              {analysing ? <Loader2 className="w-4 h-4 animate-spin" /> : <BarChart2 className="w-4 h-4" />}
              {T("Analyser tilbud")}
            </button>
          )}
          {tender.offers.length >= 1 && tender.status !== "draft" && (
            <button
              onClick={() =>
                downloadTenderPresentationPdf(
                  Number(id),
                  `tilbudsfremstilling_${tender.orgnr}.pdf`,
                )
              }
              className="flex items-center gap-1.5 px-4 py-2 border border-border text-foreground text-sm rounded-lg hover:bg-muted"
              title={T("Last ned tilbudsfremstilling for kunde")}
            >
              <FileDown className="w-4 h-4" />
              {T("Tilbudsfremstilling")}
            </button>
          )}
        </div>
      </div>

      {/* Notes */}
      {tender.notes && (
        <div className="broker-card mb-4">
          <h3 className="text-sm font-semibold text-foreground mb-1">{T("Kravspesifikasjon")}</h3>
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{tender.notes}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Recipients */}
        <div className="broker-card">
          <h3 className="text-sm font-semibold text-foreground mb-3">
            {T("Mottakere")} ({tender.recipients.length})
          </h3>
          {tender.recipients.length === 0 ? (
            <p className="text-sm text-muted-foreground">{T("Ingen mottakere lagt til.")}</p>
          ) : (
            <div className="space-y-2">
              {tender.recipients.map((r) => {
                const rs = RECIPIENT_STATUS[r.status] || RECIPIENT_STATUS.pending;
                return (
                  <div key={r.id} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
                    <div>
                      <span className="text-sm font-medium text-foreground">{r.insurer_name}</span>
                      {r.insurer_email && (
                        <span className="text-xs text-muted-foreground ml-2">{r.insurer_email}</span>
                      )}
                    </div>
                    <span className={`text-xs font-medium ${rs.cls}`}>{T(rs.labelKey)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Upload offer */}
        <div className="broker-card">
          <h3 className="text-sm font-semibold text-foreground mb-3">
            {T("Last opp tilbud")} ({tender.offers.length})
          </h3>
          <div className="space-y-3">
            <select
              className="input-sm w-full"
              value={uploadInsurer}
              onChange={(e) => setUploadInsurer(e.target.value)}
            >
              <option value="">{T("Velg forsikringsselskap...")}</option>
              {tender.recipients.map((r) => (
                <option key={r.id} value={r.insurer_name}>{r.insurer_name}</option>
              ))}
              <option value="_custom">{T("Annet selskap...")}</option>
            </select>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              onChange={handleUpload}
              disabled={!uploadInsurer || uploading}
              className="block w-full text-sm text-muted-foreground file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:bg-primary file:text-white hover:file:bg-primary/80 disabled:opacity-50"
            />
            {uploading && (
              <p className="text-xs text-primary flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" />
                {T("Laster opp og analyserer...")}
              </p>
            )}
          </div>

          {/* Uploaded offers list */}
          {tender.offers.length > 0 && (
            <div className="mt-4 space-y-2">
              {tender.offers.map((o) => (
                <div key={o.id} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-primary" />
                    <div>
                      <span className="text-sm font-medium text-foreground">{o.insurer_name}</span>
                      <span className="text-xs text-muted-foreground ml-2">{o.filename}</span>
                    </div>
                  </div>
                  {o.extracted_data ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <Clock className="w-4 h-4 text-brand-warning" />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* AI Analysis result */}
      {analysis && <AnalysisSection analysis={analysis} />}
    </div>
  );
}

/* ── Analysis rendering (extracted for clean typing) ────────────────────── */

interface AnalysisSectionProps {
  analysis: {
    anbefaling?: { forsikringsgiver: string; begrunnelse: string };
    oppsummering?: string;
    nøkkelforskjeller?: string[];
    sammenligning?: {
      kategori: string;
      felter?: {
        felt: string;
        verdier?: Record<string, string>;
        kommentar?: string;
        konfidens?: string;
      }[];
    }[];
  };
}

function AnalysisSection({ analysis }: AnalysisSectionProps) {
  const T = useT();
  return (
    <div className="broker-card">
      <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
        <BarChart2 className="w-4 h-4 text-primary" />
        {T("AI-sammenligning")}
      </h3>

      {analysis.anbefaling && (
        <div className="bg-brand-success/10 border border-green-200 rounded-lg p-4 mb-4">
          <h4 className="text-sm font-semibold text-green-800 mb-1">{T("Anbefaling")}</h4>
          <p className="text-sm text-green-700">
            <strong>{analysis.anbefaling.forsikringsgiver}</strong>
            {" — "}
            {analysis.anbefaling.begrunnelse}
          </p>
        </div>
      )}

      {analysis.oppsummering && (
        <p className="text-sm text-muted-foreground mb-4 italic">{analysis.oppsummering}</p>
      )}

      {analysis.nøkkelforskjeller && analysis.nøkkelforskjeller.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-semibold text-foreground uppercase tracking-wide mb-2">{T("Nøkkelforskjeller")}</h4>
          <ul className="space-y-1">
            {analysis.nøkkelforskjeller.map((d, i) => (
              <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-brand-warning mt-0.5 flex-shrink-0" />
                {d}
              </li>
            ))}
          </ul>
        </div>
      )}

      {analysis.sammenligning && analysis.sammenligning.length > 0 && (
        <div className="overflow-x-auto">
          {analysis.sammenligning.map((cat, ci) => {
            const firstVerdier = cat.felter?.[0]?.verdier;
            const columns = firstVerdier ? Object.keys(firstVerdier) : [];
            return (
              <div key={ci} className="mb-4">
                <h4 className="text-xs font-semibold text-foreground uppercase tracking-wide mb-2">
                  {cat.kategori}
                </h4>
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-background">
                      <th className="text-left p-2 text-xs text-muted-foreground font-medium">{T("Felt")}</th>
                      {columns.map((col) => (
                        <th key={col} className="text-left p-2 text-xs text-muted-foreground font-medium">{col}</th>
                      ))}
                      <th className="text-left p-2 text-xs text-muted-foreground font-medium">{T("Kommentar")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cat.felter?.map((f, fi) => {
                      const isLow = f.konfidens === "lav";
                      return (
                        <tr key={fi} className={`border-b border-border ${isLow ? "bg-yellow-50" : ""}`}>
                          <td className="p-2 font-medium text-foreground">{f.felt}</td>
                          {f.verdier && Object.values(f.verdier).map((v, vi) => (
                            <td key={vi} className="p-2 text-muted-foreground">{v}</td>
                          ))}
                          <td className="p-2 text-muted-foreground text-xs">
                            {f.kommentar}
                            {isLow && (
                              <span className="ml-1 text-yellow-600 font-medium">({T("lav konfidens")})</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
