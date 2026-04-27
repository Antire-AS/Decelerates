"use client";

import { useState } from "react";
import { Download, FileText, Briefcase, Rocket, Loader2 } from "lucide-react";
import { SectionHeader } from "./shared";
import { seedDemoTender } from "@/lib/api";
import { useT } from "@/lib/i18n";

/**
 * Demo-data quick access for customer demos.
 *
 * Points at raw GitHub blobs under docs/demo-data/ — no backend changes,
 * no Azure upload needed. Files come from the repo's main branch so any
 * update to the generators propagates after the next PR merge.
 *
 * Scope: 14 risk profiles (3 fictional SMBs + 11 real Norwegian
 * large caps) + 3 insurance-offer PDFs.
 */

const RAW_BASE =
  "https://raw.githubusercontent.com/Antire-AS/Decelerates/main/docs/demo-data";

type RiskProfile = {
  slug: string;
  navn: string;
  bransje: string;
  score: number;
  bucket: "lav" | "moderat" | "høy";
};

type Offer = {
  slug: string;
  navn: string;
};

const FICTIONAL_PROFILES: RiskProfile[] = [
  { slug: "bergmann_industri", navn: "Bergmann Industri AS", bransje: "Metallproduksjon", score: 6, bucket: "moderat" },
  { slug: "nordlys_restaurant", navn: "Nordlys Restaurantgruppe AS", bransje: "Restaurant, 3 lokasjoner", score: 11, bucket: "høy" },
  { slug: "arcticom_consulting", navn: "Arcticom Consulting AS", bransje: "Rådgivning", score: 3, bucket: "lav" },
];

const NORWEGIAN_PROFILES: RiskProfile[] = [
  { slug: "dnb", navn: "DNB Bank ASA", bransje: "Bank", score: 4, bucket: "lav" },
  { slug: "telenor", navn: "Telenor ASA", bransje: "Telekom", score: 5, bucket: "lav" },
  { slug: "norgesgruppen", navn: "NorgesGruppen ASA", bransje: "Dagligvare", score: 5, bucket: "lav" },
  { slug: "kongsberg", navn: "Kongsberg Gruppen ASA", bransje: "Forsvar/luftfart", score: 7, bucket: "moderat" },
  { slug: "strawberry", navn: "Strawberry Hospitality AS", bransje: "Hotel (Nordic)", score: 10, bucket: "moderat" },
  { slug: "sats", navn: "SATS Group AS", bransje: "Treningssenter", score: 8, bucket: "moderat" },
  { slug: "thon_hotels", navn: "Thon Hotels AS", bransje: "Hotel Norge", score: 6, bucket: "moderat" },
  { slug: "xxl", navn: "XXL ASA", bransje: "Sportsbutikk", score: 13, bucket: "høy" },
  { slug: "norwegian_air", navn: "Norwegian Air Shuttle ASA", bransje: "Flyselskap", score: 14, bucket: "høy" },
  { slug: "orkla", navn: "Orkla ASA", bransje: "Konsumprodukter", score: 4, bucket: "lav" },
  { slug: "vinmonopolet", navn: "AS Vinmonopolet", bransje: "Drikkevarer", score: 3, bucket: "lav" },
];

const OFFERS: Offer[] = [
  { slug: "if_skadeforsikring", navn: "If Skadeforsikring" },
  { slug: "gjensidige", navn: "Gjensidige Forsikring" },
  { slug: "tryg", navn: "Tryg Forsikring" },
];

const BUCKET_CLASS: Record<RiskProfile["bucket"], string> = {
  lav: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  moderat: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  høy: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
};


function ProfileRow({ p }: { p: RiskProfile }) {
  const T = useT();
  return (
    <tr>
      <td className="py-2 pr-3 text-foreground">{p.navn}</td>
      <td className="py-2 pr-3 text-muted-foreground text-xs">{p.bransje}</td>
      <td className="py-2 pr-3">
        <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${BUCKET_CLASS[p.bucket]}`}>
          {p.score} ({p.bucket})
        </span>
      </td>
      <td className="py-2 pr-3 text-right">
        <a
          href={`${RAW_BASE}/risk_${p.slug}.pdf`}
          download
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          aria-label={T("Last ned") + ` ${p.navn}`}
        >
          <Download className="w-3 h-3" />
          {T("Last ned")}
        </a>
      </td>
    </tr>
  );
}

function OfferRow({ o }: { o: Offer }) {
  const T = useT();
  return (
    <tr>
      <td className="py-2 pr-3 text-foreground">{o.navn}</td>
      <td className="py-2 pr-3 text-right">
        <a
          href={`${RAW_BASE}/tilbud_${o.slug}.pdf`}
          download
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          aria-label={T("Last ned") + ` ${o.navn}`}
        >
          <Download className="w-3 h-3" />
          {T("Last ned")}
        </a>
      </td>
    </tr>
  );
}

export function DemoDataSection() {
  const T = useT();
  const [seeding, setSeeding] = useState(false);
  const [seedError, setSeedError] = useState<string | null>(null);

  async function handleSeed() {
    setSeeding(true);
    setSeedError(null);
    try {
      const res = await seedDemoTender();
      window.location.assign(res.url);
    } catch (e) {
      setSeedError(String(e));
      setSeeding(false);
    }
  }

  return (
    <div className="broker-card space-y-5">
      <SectionHeader
        title={T("Demo-data")}
        subtitle={T(
          "Ferdige PDF-er for demo av hele anbud-flyten. Last ned risikoprofiler for å sende som anbudspakke, og forsikringstilbud for å simulere svar.",
        )}
      />

      {/* One-click demo-tender */}
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 flex items-center justify-between gap-3">
        <div className="flex-1">
          <p className="text-sm font-medium">{T("Start ny demo-tender")}</p>
          <p className="text-xs text-muted-foreground">
            {T(
              "Oppretter Bergmann Industri AS + anbud med 3 forsikringsselskap-mottakere (Gjensidige/If/Tryg) routet til Gmail-aliaser. Send invitasjoner og svar fra Gmail med en tilbud_*.pdf for en komplett e2e-demo.",
            )}
          </p>
          {seedError && (
            <p className="mt-1 text-[11px] text-rose-600 dark:text-rose-400">{seedError}</p>
          )}
        </div>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="inline-flex items-center gap-2 px-3 py-2 rounded bg-primary text-primary-foreground text-xs font-medium hover:opacity-90 disabled:opacity-50"
        >
          {seeding ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Rocket className="w-3.5 h-3.5" />
          )}
          {T("Start demo")}
        </button>
      </div>

      {/* Risikoprofiler - fiktive */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <FileText className="w-4 h-4 text-muted-foreground" />
          <h3 className="text-sm font-medium">{T("Risikoprofiler - fiktive SMBs")}</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">{T("Selskap")}</th>
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">{T("Bransje")}</th>
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">{T("Score")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {FICTIONAL_PROFILES.map((p) => <ProfileRow key={p.slug} p={p} />)}
            </tbody>
          </table>
        </div>
      </div>

      {/* Risikoprofiler - norske toppselskap */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <FileText className="w-4 h-4 text-muted-foreground" />
          <h3 className="text-sm font-medium">{T("Risikoprofiler - norske toppselskap")}</h3>
          <span className="text-[10px] text-muted-foreground italic">{T("(fiktive tall, reelle navn)")}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">{T("Selskap")}</th>
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">{T("Bransje")}</th>
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">{T("Score")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {NORWEGIAN_PROFILES.map((p) => <ProfileRow key={p.slug} p={p} />)}
            </tbody>
          </table>
        </div>
      </div>

      {/* Forsikringstilbud */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Briefcase className="w-4 h-4 text-muted-foreground" />
          <h3 className="text-sm font-medium">{T("Forsikringstilbud")}</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">{T("Forsikringsselskap")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {OFFERS.map((o) => <OfferRow key={o.slug} o={o} />)}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-[10px] text-muted-foreground italic">
        {T(
          "Filene serveres direkte fra GitHub (main branch). Regenerer via scripts/generate_sample_risk_profiles.py og generate_sample_offers.py.",
        )}
      </p>
    </div>
  );
}
