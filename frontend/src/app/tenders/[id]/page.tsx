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
  downloadTenderComparisonXlsx,
  generateTenderCustomerPortal,
  declineTenderRecipient,
  type Tender,
} from "@/lib/api";
import {
  ArrowLeft,
  Send,
  BarChart2,
  Bell,
  Clock,
  CheckCircle,
  Copy,
  Mail,
  X,
  FileText,
  FileDown,
  AlertTriangle,
  Loader2,
  Check,
  Star,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import TenderChatPanel from "@/components/tenders/TenderChatPanel";

// Mockup §7 from 2026-04-25 polish plan: 5-step horizontal indicator at the
// top of /tenders/[id]. Per CLAUDE.md UX rule (F07/F19 audit): use ✓ for
// completed, ● for active, empty circle for upcoming — never numbers.
type StepStatus = "done" | "active" | "upcoming";

function TenderStepTracker({ tender }: { tender: Tender }) {
  const T = useT();
  const recipients = tender.recipients ?? [];
  const offers = tender.offers ?? [];
  const hasReceivedOffer =
    recipients.some((r) => r.status === "received") || offers.length > 0;

  const stepDoneFlags: boolean[] = [
    true,                                  // Behovsanalyse — implicit on tender creation
    recipients.length > 0,                 // Anbudspakke — package has recipients
    tender.status !== "draft",             // Sendt — moved out of draft
    hasReceivedOffer,                      // Mottatt — at least one offer back
    tender.status === "analysed",          // Sammenligning — AI analysis done
  ];
  const labels = ["Behovsanalyse", "Anbudspakke", "Sendt", "Mottatt", "Sammenligning"];

  const firstIncomplete = stepDoneFlags.findIndex((d) => !d);
  const stepStatuses: StepStatus[] = stepDoneFlags.map((done, i) => {
    if (done) return "done";
    if (i === firstIncomplete) return "active";
    return "upcoming";
  });

  return (
    <ol className="flex items-start w-full mb-6" aria-label={T("Anbudsforløp")}>
      {labels.map((label, i) => {
        const status = stepStatuses[i];
        const isLast = i === labels.length - 1;
        return (
          <li key={label} className={cn("flex items-start", !isLast && "flex-1")}>
            <div className="flex flex-col items-center text-center min-w-0">
              <div
                aria-current={status === "active" ? "step" : undefined}
                className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 border-2 transition-colors",
                  status === "done" && "bg-primary border-primary text-primary-foreground",
                  status === "active" && "bg-background border-primary text-primary",
                  status === "upcoming" && "bg-background border-border text-transparent",
                )}
              >
                {status === "done" && <Check className="w-4 h-4" aria-hidden />}
                {status === "active" && (
                  <span className="w-2 h-2 rounded-full bg-primary" aria-hidden />
                )}
              </div>
              <span
                className={cn(
                  "text-[11px] mt-1.5 px-1 max-w-[88px] leading-tight",
                  status === "done" && "text-foreground font-medium",
                  status === "active" && "text-foreground font-semibold",
                  status === "upcoming" && "text-muted-foreground",
                )}
              >
                {T(label)}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  "flex-1 h-0.5 mt-3 mx-1.5",
                  stepDoneFlags[i] ? "bg-primary" : "bg-border",
                )}
                aria-hidden
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

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

const DECLINE_REASON_LABEL: Record<string, string> = {
  capacity: "Kapasitet",
  bad_match: "Dårlig anbud",
  high_risk: "Høy risiko",
  other: "Annet",
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
  const [showCustomerDialog, setShowCustomerDialog] = useState(false);
  const [customerEmail, setCustomerEmail] = useState("");
  const [mintingCustomerLink, setMintingCustomerLink] = useState(false);
  const [customerLinkPath, setCustomerLinkPath] = useState<string | null>(null);

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

  async function handleMintCustomerLink() {
    if (!customerEmail) return;
    setMintingCustomerLink(true);
    try {
      const res = await generateTenderCustomerPortal(Number(id), {
        customer_email: customerEmail,
      });
      const fullUrl = `${window.location.origin}${res.portal_url_path}`;
      setCustomerLinkPath(fullUrl);
      await mutate();
    } catch {
      toast.error(T("Kunne ikke generere kundelenke"));
    } finally {
      setMintingCustomerLink(false);
    }
  }

  function openCustomerDialog() {
    setCustomerEmail(tender?.customer_email ?? "");
    if (tender?.customer_access_token) {
      setCustomerLinkPath(
        `${window.location.origin}/portal/tender/${tender.customer_access_token}`,
      );
    } else {
      setCustomerLinkPath(null);
    }
    setShowCustomerDialog(true);
  }

  async function copyCustomerLink() {
    if (!customerLinkPath) return;
    try {
      await navigator.clipboard.writeText(customerLinkPath);
      toast.success(T("Lenke kopiert"));
    } catch {
      toast.error(T("Kunne ikke kopiere"));
    }
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

      <TenderStepTracker tender={tender} />

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
          {tender.analysis_result && (
            <button
              onClick={() =>
                downloadTenderComparisonXlsx(
                  Number(id),
                  `sammenligning_${tender.orgnr}.xlsx`,
                )
              }
              className="flex items-center gap-1.5 px-4 py-2 border border-border text-foreground text-sm rounded-lg hover:bg-muted"
              title={T("Last ned AI-sammenligning som Excel")}
            >
              <FileDown className="w-4 h-4" />
              {T("Eksporter Excel")}
            </button>
          )}
          {tender.analysis_result && (
            <button
              onClick={openCustomerDialog}
              className="flex items-center gap-1.5 px-4 py-2 border border-primary/30 text-primary bg-primary/5 text-sm rounded-lg hover:bg-primary/10"
              title={T("Generer en lenke kunden kan åpne for å godkjenne tilbudet")}
            >
              <Mail className="w-4 h-4" />
              {tender.customer_access_token
                ? T("Vis kundelenke")
                : T("Send til kunde")}
            </button>
          )}
        </div>
      </div>

      {/* Customer portal dialog */}
      {showCustomerDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-card rounded-2xl shadow-2xl max-w-md w-full">
            <div className="bg-primary px-6 py-4 flex items-center justify-between rounded-t-2xl">
              <h2 className="text-white font-semibold">{T("Kundelenke")}</h2>
              <button
                onClick={() => setShowCustomerDialog(false)}
                className="text-white/70 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-xs text-muted-foreground">
                {T(
                  "Generer en privat lenke til kunden. De ser AI-anbefalingen og sammenligningen, og kan godkjenne eller avslå.",
                )}
              </p>
              <div>
                <label className="label-xs" htmlFor="customer-email">
                  {T("Kundens e-post")}
                </label>
                <input
                  id="customer-email"
                  type="email"
                  className="input-sm w-full"
                  placeholder="kunde@firma.no"
                  value={customerEmail}
                  onChange={(e) => setCustomerEmail(e.target.value)}
                />
              </div>
              {customerLinkPath && (
                <div className="rounded-lg border border-border bg-muted px-3 py-2 flex items-center gap-2">
                  <code className="text-[10px] flex-1 truncate text-foreground">
                    {customerLinkPath}
                  </code>
                  <button
                    onClick={copyCustomerLink}
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                  >
                    <Copy className="w-3 h-3" />
                    {T("Kopier")}
                  </button>
                </div>
              )}
              {tender.customer_approval_status && (
                <p className="text-xs">
                  {T("Status")}:{" "}
                  <strong
                    className={
                      tender.customer_approval_status === "approved"
                        ? "text-emerald-600"
                        : tender.customer_approval_status === "rejected"
                          ? "text-rose-600"
                          : "text-muted-foreground"
                    }
                  >
                    {tender.customer_approval_status === "approved"
                      ? T("Godkjent")
                      : tender.customer_approval_status === "rejected"
                        ? T("Avslått")
                        : T("Venter")}
                  </strong>
                </p>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowCustomerDialog(false)}
                  className="px-4 py-2 border border-border text-foreground text-sm rounded-lg hover:bg-muted"
                >
                  {T("Lukk")}
                </button>
                <button
                  onClick={handleMintCustomerLink}
                  disabled={mintingCustomerLink || !customerEmail}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/90 disabled:opacity-50"
                >
                  {mintingCustomerLink && (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  )}
                  {tender.customer_access_token
                    ? T("Oppdater e-post")
                    : T("Generer lenke")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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
                const declineLabel = r.decline_reason ? DECLINE_REASON_LABEL[r.decline_reason] : null;
                const canDecline = r.status === "pending" || r.status === "sent";
                return (
                  <div key={r.id} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
                    <div>
                      <span className="text-sm font-medium text-foreground">{r.insurer_name}</span>
                      {r.insurer_email && (
                        <span className="text-xs text-muted-foreground ml-2">{r.insurer_email}</span>
                      )}
                      {r.status === "declined" && declineLabel && (
                        <span
                          className="ml-2 inline-block px-1.5 py-0.5 rounded bg-red-50 text-red-700 text-[10px] font-medium"
                          title={r.decline_note ?? undefined}
                        >
                          {T(declineLabel)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium ${rs.cls}`}>{T(rs.labelKey)}</span>
                      {canDecline && (
                        <select
                          aria-label={T("Marker som avslått")}
                          defaultValue=""
                          className="text-[10px] px-1 py-0.5 rounded border border-border bg-background text-muted-foreground hover:text-foreground"
                          onChange={async (e) => {
                            const reason = e.target.value as
                              | "capacity"
                              | "bad_match"
                              | "high_risk"
                              | "other"
                              | "";
                            if (!reason) return;
                            await declineTenderRecipient(tender.id, r.id, { reason });
                            await mutate();
                          }}
                        >
                          <option value="">{T("Avslå…")}</option>
                          <option value="capacity">{T("Kapasitet")}</option>
                          <option value="bad_match">{T("Dårlig anbud")}</option>
                          <option value="high_risk">{T("Høy risiko")}</option>
                          <option value="other">{T("Annet")}</option>
                        </select>
                      )}
                    </div>
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

// Mockup §9 polish helpers. Detects which field-type expects "lower is better"
// (price-style) vs "higher is better" (coverage-style). Norwegian terms; exact
// match is fine since the Gemini comparison schema uses canonical field names.
function fieldDirection(felt: string): "lower" | "higher" | null {
  const f = felt.toLowerCase();
  if (/premie|pris|kostnad|egenandel/.test(f)) return "lower";
  if (/sum|grense|dekning|maks/.test(f)) return "higher";
  return null;
}

// Parse a Norwegian-formatted currency or number string. Returns null if the
// value isn't a clean number (e.g. "Inkludert", "På forespørsel").
function parseNok(v: string): number | null {
  const cleaned = v.replace(/[^\d,.\-]/g, "").replace(/\s/g, "").replace(",", ".");
  if (!cleaned) return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

function AnalysisSection({ analysis }: AnalysisSectionProps) {
  const T = useT();
  const recommended = analysis.anbefaling?.forsikringsgiver?.trim();

  return (
    <div className="broker-card">
      <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
        <BarChart2 className="w-4 h-4 text-primary" />
        {T("AI-sammenligning")}
      </h3>

      {analysis.anbefaling && (
        <div className="bg-brand-success/10 border border-green-200 rounded-lg p-4 mb-4">
          <h4 className="text-sm font-semibold text-green-800 mb-1 flex items-center gap-1.5">
            <Star className="w-4 h-4 fill-current" aria-hidden />
            {T("Anbefaling")}
          </h4>
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
                      {columns.map((col) => {
                        const isRec = recommended === col;
                        return (
                          <th
                            key={col}
                            className={`text-left p-2 text-xs font-medium ${
                              isRec
                                ? "text-green-800 bg-brand-success/10"
                                : "text-muted-foreground"
                            }`}
                          >
                            <span className="inline-flex items-center gap-1">
                              {isRec && <Star className="w-3 h-3 text-green-700 fill-current" aria-hidden />}
                              {col}
                            </span>
                          </th>
                        );
                      })}
                      <th className="text-left p-2 text-xs text-muted-foreground font-medium">{T("Kommentar")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cat.felter?.map((f, fi) => {
                      const isLow = f.konfidens === "lav";
                      // Best-cell highlight: only on rows where the field name
                      // implies a clear "lower/higher is better" semantic AND
                      // we can parse ≥2 numeric values across columns.
                      const direction = fieldDirection(f.felt);
                      const numericByCol: Record<string, number> = {};
                      if (direction && f.verdier) {
                        for (const [col, v] of Object.entries(f.verdier)) {
                          const n = parseNok(v);
                          if (n !== null) numericByCol[col] = n;
                        }
                      }
                      const numericCols = Object.keys(numericByCol);
                      let bestCol: string | null = null;
                      if (direction && numericCols.length >= 2) {
                        bestCol = numericCols.reduce((best, col) =>
                          (direction === "lower"
                            ? numericByCol[col] < numericByCol[best]
                            : numericByCol[col] > numericByCol[best])
                            ? col
                            : best,
                        );
                      }
                      return (
                        <tr key={fi} className={`border-b border-border ${isLow ? "bg-yellow-50" : ""}`}>
                          <td className="p-2 font-medium text-foreground">{f.felt}</td>
                          {f.verdier && columns.map((col) => {
                            const v = f.verdier?.[col] ?? "";
                            const isRec = recommended === col;
                            const isBest = bestCol === col;
                            return (
                              <td
                                key={col}
                                className={`p-2 ${
                                  isBest
                                    ? "text-green-800 font-semibold bg-brand-success/10"
                                    : isRec
                                      ? "text-foreground bg-brand-success/5"
                                      : "text-muted-foreground"
                                }`}
                                title={isBest ? T("Beste verdi i denne raden") : undefined}
                              >
                                {v}
                              </td>
                            );
                          })}
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

      <TenderChatPanel
        tender={{
          title: tender.title,
          orgnr: tender.orgnr,
          product_types: tender.product_types,
          deadline: tender.deadline,
          recipient_count: tender.recipients.length,
          offer_count: tender.offers.length,
          status: tender.status,
        }}
      />
    </div>
  );
}
