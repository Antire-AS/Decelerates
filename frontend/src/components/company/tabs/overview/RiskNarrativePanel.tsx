"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";
import { generateNarrative } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Section } from "./shared";

interface Props {
  orgnr: string;
}

// LocalStorage key prefix — the narrative is deterministic for a given
// (orgnr, payload) so caching client-side prevents a fresh LLM roundtrip
// every tab-switch. Evicted when the user clicks Regenerer.
const CACHE_PREFIX = "narrative-v1:";

function loadCached(orgnr: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(CACHE_PREFIX + orgnr);
  } catch {
    return null;
  }
}

function saveCached(orgnr: string, text: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(CACHE_PREFIX + orgnr, text);
  } catch {
    // quota exceeded or storage disabled — harmless, we just regen next time
  }
}

function clearCached(orgnr: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(CACHE_PREFIX + orgnr);
  } catch {
    // ignore
  }
}

function Skeleton() {
  return (
    <div className="space-y-2" aria-label="Laster narrative">
      <div className="h-3 bg-muted rounded animate-pulse w-5/6" />
      <div className="h-3 bg-muted rounded animate-pulse w-full" />
      <div className="h-3 bg-muted rounded animate-pulse w-4/6" />
      <div className="h-3 bg-muted rounded animate-pulse w-3/4" />
    </div>
  );
}

export default function RiskNarrativePanel({ orgnr }: Props) {
  const T = useT();
  const [narrative, setNarrative] = useState<string | null>(() => loadCached(orgnr));
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(
    async (force: boolean) => {
      setLoading(true);
      setErr(null);
      try {
        const r = await generateNarrative(orgnr);
        setNarrative(r.narrative);
        saveCached(orgnr, r.narrative);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setErr(msg);
        if (force) clearCached(orgnr);
      } finally {
        setLoading(false);
      }
    },
    [orgnr],
  );

  // Auto-fetch on mount when there's no cached narrative. Cached narratives
  // are displayed instantly — broker can press Regenerer if they want a
  // fresher take (e.g. after adding a PDF year).
  useEffect(() => {
    const cached = loadCached(orgnr);
    if (cached) {
      setNarrative(cached);
    } else {
      run(false);
    }
  }, [orgnr, run]);

  return (
    <Section title={T("AI-risikoanalyse")}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Sparkles className="w-3.5 h-3.5" />
          <span>{T("Generert sammendrag — Altman, peers og regelfaktorer")}</span>
        </div>
        <button
          onClick={() => run(true)}
          disabled={loading}
          className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded border border-muted-foreground/20 hover:bg-muted disabled:opacity-50"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          {T("Regenerer")}
        </button>
      </div>
      {err && (
        <p className="text-xs text-red-600 mb-2">{err}</p>
      )}
      {loading && !narrative ? (
        <Skeleton />
      ) : narrative ? (
        <p className="text-xs text-foreground whitespace-pre-wrap leading-relaxed">
          {narrative}
        </p>
      ) : (
        !err && (
          <p className="text-xs text-muted-foreground">
            {T("Trykk «Regenerer» for å generere en AI-risikoanalyse.")}
          </p>
        )
      )}
    </Section>
  );
}
