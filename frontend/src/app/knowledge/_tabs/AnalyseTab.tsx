"use client";

import { useState } from "react";
import { Loader2, BarChart3, Download, Trash2 } from "lucide-react";
import { knowledgeChat } from "@/lib/api";
import {
  readableSource, extractMarkdownTables, tableToCsv, downloadCsv, renderMarkdownWithTables,
} from "./_shared";
import { useT } from "@/lib/i18n";

const COMPARISON_PROMPTS: Array<{ label: string; prompt: string }> = [
  {
    label: "📊 Sammenlign ansvarsforsikring og produktansvar",
    prompt: "Lag en kompakt sammenligningstabell (markdown) av ansvarsforsikring og produktansvarsforsikring " +
            "med kolonner: Type | Hva dekkes | Typiske unntak | Hvem trenger det.",
  },
  {
    label: "📊 Oversikt over vanlige bedriftsforsikringer",
    prompt: "Lag en oversiktstabell (markdown) over de 6 vanligste forsikringstypene for norske SMB-bedrifter " +
            "med kolonner: Forsikringstype | Hva dekkes | Typisk forsikringssum | Anbefalt for.",
  },
  {
    label: "📊 Cyberforsikring — dekning og unntak",
    prompt: "Lag en tabell (markdown) over hva cyberforsikring typisk dekker og ikke dekker, " +
            "med kolonner: Område | Dekket? | Eksempel.",
  },
  {
    label: "📊 Sammenlign forsikringstilbydere i dokumentene",
    prompt: "Basert på forsikringsdokumentene i kunnskapsbasen, lag en sammenligningstabell av " +
            "forsikringstilbyderne med kolonner: Selskap | Produkt | Dekning | Premie | Særtrekk.",
  },
  {
    label: "📊 Forsikringslovgivning — nøkkelparagrafer",
    prompt: "Lag en oversiktstabell (markdown) over de viktigste paragrafene i Forsikringsavtaleloven (FAL) " +
            "som er relevante for bedriftsforsikring, med kolonner: § | Tema | Hva det innebærer.",
  },
];

interface AnalyseResult {
  label: string;
  answer: string;
  sources?: string[];
}

export default function AnalyseTab() {
  const T = useT();
  const [result, setResult]   = useState<AnalyseResult | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError]     = useState<string | null>(null);

  async function handleRun(label: string, prompt: string) {
    setLoading(label);
    setError(null);
    try {
      const res = await knowledgeChat(prompt);
      setResult({ label, answer: res.answer, sources: res.sources });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  }

  const tables = result ? extractMarkdownTables(result.answer) : [];

  return (
    <div className="space-y-4">
      <div className="broker-card space-y-2">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <BarChart3 className="w-4 h-4" /> {T("AI-genererte sammenligninger og tabeller")}
        </h3>
        <p className="text-xs text-muted-foreground">
          {T("Klikk en knapp for å be AI-en lage en strukturert tabell basert på kunnskapsbasen. Tabeller kan lastes ned som CSV.")}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {COMPARISON_PROMPTS.map(({ label, prompt }) => (
          <button
            key={label}
            onClick={() => handleRun(label, prompt)}
            disabled={loading !== null}
            className="px-4 py-3 text-left text-sm rounded-lg border border-border hover:border-primary hover:bg-accent disabled:opacity-50 transition-colors text-foreground font-medium flex items-center justify-between gap-2"
          >
            <span>{T(label)}</span>
            {loading === label && <Loader2 className="w-3.5 h-3.5 animate-spin text-primary flex-shrink-0" />}
          </button>
        ))}
      </div>

      {error && (
        <div className="broker-card bg-red-50 border-red-200 text-red-700 text-sm">{error}</div>
      )}

      {result && (
        <div className="broker-card space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-foreground">{T(result.label)}</h4>
            <button
              onClick={() => setResult(null)}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              <Trash2 className="w-3 h-3" /> {T("Tøm")}
            </button>
          </div>

          {renderMarkdownWithTables(result.answer)}

          {tables.length > 0 && (
            <div className="flex gap-2 flex-wrap pt-2 border-t border-border">
              {tables.map((rows, i) => (
                <button
                  key={i}
                  onClick={() => downloadCsv(`sammenligning_${i + 1}.csv`, tableToCsv(rows))}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-border text-primary bg-accent hover:bg-accent"
                >
                  <Download className="w-3 h-3" />
                  {T("Last ned tabell")} {i + 1} (CSV)
                </button>
              ))}
            </div>
          )}

          {result.sources && result.sources.length > 0 && (
            <details className="pt-2 border-t border-border">
              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                {T("Kilder")} ({result.sources.length})
              </summary>
              <div className="mt-2 space-y-1">
                {result.sources.map((src, i) => (
                  <p key={i} className="text-xs text-muted-foreground">• {readableSource(src)}</p>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
