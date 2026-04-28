"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { CheckCircle, XCircle, Loader2, BarChart2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import {
  getTenderCustomerView,
  recordTenderCustomerDecision,
  type TenderCustomerView,
} from "@/lib/api";
import { useT } from "@/lib/i18n";

/**
 * Customer-facing offer portal — opened via /portal/tender/<token>.
 * No auth: the unique token IS the auth boundary (FIRM_ID_AUDIT
 * annotated on the matching backend service methods).
 */

interface AnalysisField {
  felt: string;
  verdier?: Record<string, string>;
  kommentar?: string;
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

export default function CustomerOfferPortalPage() {
  const T = useT();
  const { token } = useParams<{ token: string }>();
  const { data, mutate, error, isLoading } = useSWR<TenderCustomerView>(
    `customer-portal-${token}`,
    () => getTenderCustomerView(token),
  );
  const [submitting, setSubmitting] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-xl mx-auto py-16 px-6 text-center">
        <AlertTriangle className="w-10 h-10 text-rose-500 mx-auto mb-3" />
        <h1 className="text-lg font-semibold mb-1">{T("Lenken er ugyldig")}</h1>
        <p className="text-sm text-muted-foreground">
          {T("Kontakt megleren for å få en ny lenke.")}
        </p>
      </div>
    );
  }

  const analysis = data.analysis as AnalysisResult | undefined;
  const decided = data.customer_approval_status === "approved" ||
    data.customer_approval_status === "rejected";

  async function decide(status: "approved" | "rejected") {
    setSubmitting(true);
    try {
      await recordTenderCustomerDecision(token, { status });
      await mutate();
      toast.success(
        status === "approved" ? T("Takk for godkjenningen") : T("Avslag registrert"),
      );
    } catch {
      toast.error(T("Noe gikk galt — prøv igjen"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto py-10 px-4">
      <header className="mb-8">
        <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
          {T("Tilbudsfremstilling")}
        </p>
        <h1 className="text-2xl font-bold text-foreground">{data.title}</h1>
        {data.company_name && (
          <p className="text-sm text-muted-foreground mt-1">{data.company_name}</p>
        )}
        {data.product_types.length > 0 && (
          <p className="text-xs text-muted-foreground mt-2">
            {data.product_types.join(" · ")}
          </p>
        )}
      </header>

      {analysis?.anbefaling && (
        <section className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mb-6 dark:bg-emerald-900/20 dark:border-emerald-800">
          <h2 className="text-sm font-semibold text-emerald-800 dark:text-emerald-200 mb-1">
            {T("Meglerens anbefaling")}
          </h2>
          <p className="text-sm text-emerald-900 dark:text-emerald-100">
            <strong>{analysis.anbefaling.forsikringsgiver}</strong> —{" "}
            {analysis.anbefaling.begrunnelse}
          </p>
        </section>
      )}

      {analysis?.oppsummering && (
        <p className="text-sm italic text-muted-foreground mb-6">
          {analysis.oppsummering}
        </p>
      )}

      {analysis?.nøkkelforskjeller && analysis.nøkkelforskjeller.length > 0 && (
        <section className="mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-wide mb-2">
            {T("Viktige forskjeller")}
          </h2>
          <ul className="space-y-1">
            {analysis.nøkkelforskjeller.map((d, i) => (
              <li key={i} className="text-sm flex items-start gap-2">
                <span className="text-amber-500 mt-0.5">•</span>
                {d}
              </li>
            ))}
          </ul>
        </section>
      )}

      {analysis?.sammenligning && analysis.sammenligning.length > 0 ? (
        <section className="mb-8">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-primary" />
            {T("Sammenligning")}
          </h2>
          {analysis.sammenligning.map((cat, ci) => {
            const cols = Object.keys(cat.felter?.[0]?.verdier ?? {});
            return (
              <div key={ci} className="mb-4 overflow-x-auto">
                <h3 className="text-xs font-semibold uppercase mb-2">
                  {cat.kategori}
                </h3>
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-muted">
                      <th className="text-left p-2 text-xs">{T("Felt")}</th>
                      {cols.map((c) => (
                        <th key={c} className="text-left p-2 text-xs">{c}</th>
                      ))}
                      <th className="text-left p-2 text-xs">{T("Kommentar")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cat.felter?.map((f, fi) => (
                      <tr key={fi} className="border-b border-border">
                        <td className="p-2 font-medium">{f.felt}</td>
                        {cols.map((c) => (
                          <td key={c} className="p-2 text-muted-foreground">
                            {f.verdier?.[c] ?? "—"}
                          </td>
                        ))}
                        <td className="p-2 text-muted-foreground text-xs">
                          {f.kommentar}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </section>
      ) : (
        <p className="text-sm text-muted-foreground italic mb-8">
          {T("Megleren har ikke kjørt analysen ennå.")}
        </p>
      )}

      <section className="border-t border-border pt-6">
        {decided ? (
          <div className="text-center py-6">
            {data.customer_approval_status === "approved" ? (
              <>
                <CheckCircle className="w-10 h-10 text-emerald-600 mx-auto mb-2" />
                <p className="text-sm font-medium">{T("Du har godkjent dette tilbudet")}</p>
              </>
            ) : (
              <>
                <XCircle className="w-10 h-10 text-rose-600 mx-auto mb-2" />
                <p className="text-sm font-medium">{T("Du har avslått dette tilbudet")}</p>
              </>
            )}
            {data.customer_approval_at && (
              <p className="text-xs text-muted-foreground mt-1">
                {new Date(data.customer_approval_at).toLocaleString("no-NB")}
              </p>
            )}
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row gap-3 justify-end">
            <button
              onClick={() => decide("rejected")}
              disabled={submitting}
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 border border-border text-foreground text-sm rounded-lg hover:bg-muted disabled:opacity-50"
            >
              <XCircle className="w-4 h-4" />
              {T("Avslå")}
            </button>
            <button
              onClick={() => decide("approved")}
              disabled={submitting}
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/90 disabled:opacity-50"
            >
              {submitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle className="w-4 h-4" />
              )}
              {T("Godkjenn")}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
