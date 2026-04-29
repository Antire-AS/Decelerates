"use client";

import { use, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import useSWR from "swr";
import { ArrowLeft, FileDown, Loader2 } from "lucide-react";
import { getOrgProfile, type OrgProfile } from "@/lib/api";
import PdfPreviewPane from "@/components/forsikringstilbud/PdfPreviewPane";
import { useT } from "@/lib/i18n";

interface SessionWithToken {
  idToken?: string;
}

export default function ForsikringstilbudPage({
  params,
}: {
  params: Promise<{ orgnr: string }>;
}) {
  const { orgnr } = use(params);
  const T = useT();
  const { data: sess } = useSession();
  const idToken = (sess as SessionWithToken | null)?.idToken;

  const { data: prof } = useSWR<OrgProfile>(
    `org-${orgnr}`,
    () => getOrgProfile(orgnr),
  );

  const [sammendrag, setSammendrag] = useState("");
  const [premieanslag, setPremieanslag] = useState("");
  const [anbefalingerText, setAnbefalingerText] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [downloadErr, setDownloadErr] = useState<string | null>(null);

  const payload = useMemo(
    () => ({
      sammendrag: sammendrag.trim(),
      total_premieanslag: premieanslag.trim(),
      anbefalinger: anbefalingerText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    }),
    [sammendrag, premieanslag, anbefalingerText],
  );

  async function handleDownload() {
    setDownloading(true);
    setDownloadErr(null);
    try {
      const res = await fetch(`/bapi/org/${orgnr}/forsikringstilbud/pdf?save=true`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `forsikringstilbud_${orgnr}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setDownloadErr(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloading(false);
    }
  }

  const orgName = prof?.org?.navn ? String(prof.org.navn) : orgnr;

  return (
    <div className="space-y-5">
      <Link
        href={`/search/${orgnr}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="w-4 h-4" />
        {T("Tilbake til selskap")}
      </Link>

      <div>
        <h1 className="text-2xl font-bold text-foreground">{T("Forsikringstilbud")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {T("Generer profesjonelle tilbudsdokumenter med din meglerbranding")} ·{" "}
          <span className="font-medium text-foreground">{orgName}</span>
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Form (left) */}
        <div className="space-y-4">
          <div className="broker-card space-y-3">
            <h2 className="text-sm font-semibold text-foreground">{T("Sammendrag")}</h2>
            <textarea
              value={sammendrag}
              onChange={(e) => setSammendrag(e.target.value)}
              rows={4}
              placeholder={T("Kort beskrivelse av tilbudet, anbefalt dekning, forutsetninger…")}
              className="w-full text-sm px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="broker-card space-y-3">
            <h2 className="text-sm font-semibold text-foreground">{T("Total premieanslag")}</h2>
            <input
              value={premieanslag}
              onChange={(e) => setPremieanslag(e.target.value)}
              placeholder={T("Eksempel: kr 1 185 000")}
              className="w-full text-sm px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="broker-card space-y-3">
            <h2 className="text-sm font-semibold text-foreground">{T("Anbefalinger")}</h2>
            <p className="text-xs text-muted-foreground">
              {T("Én anbefaling per linje")}
            </p>
            <textarea
              value={anbefalingerText}
              onChange={(e) => setAnbefalingerText(e.target.value)}
              rows={6}
              placeholder={T("Bygningsforsikring 85 MNOK\nMaskinforsikring inkludert\nAvbruddsforsikring 18 mnd\nProfesjonsansvar 50 MNOK")}
              className="w-full text-sm px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary font-mono"
            />
          </div>

          <button
            onClick={handleDownload}
            disabled={downloading}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {downloading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <FileDown className="w-4 h-4" />
            )}
            {T("Generer og last ned PDF")}
          </button>
          {downloadErr && <p className="text-xs text-red-600">{downloadErr}</p>}
        </div>

        {/* Preview (right) */}
        <PdfPreviewPane
          endpoint={`/org/${orgnr}/forsikringstilbud/pdf`}
          payload={payload}
          authToken={idToken}
        />
      </div>
    </div>
  );
}
