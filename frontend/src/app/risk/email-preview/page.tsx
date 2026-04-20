"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import { getOrgProfile } from "@/lib/api";
import type { OrgProfile } from "@/lib/api";
import { Mail, ArrowLeft, Building, FileText, CheckCircle2 } from "lucide-react";
import { useT } from "@/lib/i18n";

/**
 * Broker → client risk-email preview.
 *
 * Built as a sales/demo surface: shows the email a broker would send to a
 * client with their risk-profile summary, plus the downstream insurer
 * response mock. The visual is the key product — this isn't a live mail
 * send, it's a "here's what the flow looks like" page.
 *
 * Query params:
 *   ?orgnr=984851006  → populate with real company data (BRREG + risk score)
 *   (none)            → show demo placeholder values
 */
function RiskEmailPreviewContent() {
  const T = useT();
  const params = useSearchParams();
  const orgnr = params.get("orgnr") || "";

  const { data: prof } = useSWR<OrgProfile | null>(
    orgnr ? `org-${orgnr}` : null,
    () => (orgnr ? getOrgProfile(orgnr) : Promise.resolve(null)),
  );

  const rs = (prof?.risk_summary ?? {}) as Record<string, unknown>;
  const orgName: string = String(prof?.org?.navn ?? T("Demo AS"));
  const riskScore = Number(rs.score ?? 12);
  const riskBand: string = String(rs.band ?? "Moderat");
  const revenue = Number(rs.revenue ?? 42_500_000);
  const equityRatio = Number(rs.equity_ratio ?? 0.38);

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/search"
          className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1.5"
        >
          <ArrowLeft className="w-4 h-4" />
          {T("Tilbake")}
        </Link>
        <span className="text-xs px-2 py-1 rounded bg-accent text-accent-foreground font-medium">
          {T("Demo-visning")}
        </span>
      </div>

      <div>
        <h1 className="text-2xl font-semibold text-foreground flex items-center gap-2">
          <Mail className="w-6 h-6" /> {T("Risikoprofil-e-post")}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {T("Slik ser flyten ut: megler sender risikoprofil → forsikringsselskapet svarer med tilbud")}.
          {orgnr
            ? ` ${T("Viser reelle data for")} ${orgName}.`
            : ` ${T("Legg til")} ?orgnr=984851006 ${T("for å se reelle data")}.`}
        </p>
      </div>

      {/* Email mock */}
      <article className="broker-card p-6 space-y-4 border-l-4 border-primary">
        <div className="space-y-1 pb-3 border-b border-border">
          <div className="flex gap-2 text-xs">
            <span className="text-muted-foreground w-16">{T("Fra")}:</span>
            <span className="text-foreground">megler@meglerai.no</span>
          </div>
          <div className="flex gap-2 text-xs">
            <span className="text-muted-foreground w-16">{T("Til")}:</span>
            <span className="text-foreground">post@{orgName.toLowerCase().replace(/\s+/g, "")}.no</span>
          </div>
          <div className="flex gap-2 text-xs">
            <span className="text-muted-foreground w-16">{T("Emne")}:</span>
            <span className="text-foreground font-medium">
              {T("Risikoprofil for")} {orgName}
            </span>
          </div>
        </div>

        <div className="text-sm text-foreground space-y-3 leading-relaxed">
          <p>{T("Hei")},</p>
          <p>
            {T("Vi har gjennomført en risikovurdering av")} <strong>{orgName}</strong>{" "}
            {T("og oppsummerer her hovedpunktene før vi henter inn tilbud fra forsikringsselskapene")}.
          </p>

          <div className="bg-muted rounded-lg p-4 space-y-2">
            <div className="flex justify-between items-baseline">
              <span className="text-xs text-muted-foreground">{T("Risikoscore")}</span>
              <span className="font-semibold text-foreground">
                {riskScore}/20 · {riskBand}
              </span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="text-xs text-muted-foreground">{T("Omsetning")}</span>
              <span className="font-medium text-foreground">
                {(revenue / 1_000_000).toFixed(1)} MNOK
              </span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="text-xs text-muted-foreground">{T("Egenkapitalandel")}</span>
              <span className="font-medium text-foreground">
                {(equityRatio * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <p>
            {T("Basert på dette anslår vi en")} <strong>{T("moderat risikoprofil")}</strong>.{" "}
            {T("Vi sender nå anbudsforespørsel til aktuelle forsikringsselskaper og kommer tilbake med tilbud innen en uke")}.
          </p>
          <p>
            {T("Vedlagt")}:{" "}
            <span className="inline-flex items-center gap-1 text-primary underline">
              <FileText className="w-3.5 h-3.5" /> risikorapport_{orgnr || "demo"}.pdf
            </span>
          </p>
          <p className="text-muted-foreground text-xs pt-2">
            {T("Med vennlig hilsen")},
            <br />
            Antire Megling · meglerai.no
          </p>
        </div>
      </article>

      {/* Arrow + insurer response mock */}
      <div className="flex items-center gap-3 px-6">
        <div className="flex-1 border-t border-dashed border-border" />
        <span className="text-xs text-muted-foreground">
          {T("~3–5 dager senere")}
        </span>
        <div className="flex-1 border-t border-dashed border-border" />
      </div>

      <article className="broker-card p-6 space-y-4 border-l-4 border-green-600">
        <div className="space-y-1 pb-3 border-b border-border">
          <div className="flex gap-2 text-xs">
            <span className="text-muted-foreground w-16">{T("Fra")}:</span>
            <span className="text-foreground">bedrift@gjensidige.no</span>
          </div>
          <div className="flex gap-2 text-xs">
            <span className="text-muted-foreground w-16">{T("Emne")}:</span>
            <span className="text-foreground font-medium">
              {T("Tilbud")} — {orgName}
            </span>
          </div>
        </div>
        <div className="text-sm text-foreground space-y-3 leading-relaxed">
          <p>
            {T("Basert på risikoprofilen tilbyr vi")} <strong>{orgName}</strong>{" "}
            {T("følgende dekning")}:
          </p>
          <div className="bg-muted rounded-lg p-4 grid grid-cols-2 gap-4 text-xs">
            <div>
              <Building className="w-4 h-4 text-muted-foreground mb-1" />
              <p className="text-muted-foreground">{T("Ansvarsforsikring")}</p>
              <p className="font-semibold text-foreground">48 500 kr/år</p>
            </div>
            <div>
              <CheckCircle2 className="w-4 h-4 text-green-600 mb-1" />
              <p className="text-muted-foreground">{T("Yrkesskade")}</p>
              <p className="font-semibold text-foreground">22 800 kr/år</p>
            </div>
          </div>
          <p className="text-muted-foreground text-xs pt-2">{T("Gyldig tilbud i 30 dager")}.</p>
        </div>
      </article>
    </div>
  );
}

export default function RiskEmailPreviewPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Laster…</div>}>
      <RiskEmailPreviewContent />
    </Suspense>
  );
}
