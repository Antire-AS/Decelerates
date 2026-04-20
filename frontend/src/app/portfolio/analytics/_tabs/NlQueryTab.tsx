"use client";

import { useState } from "react";
import { Loader2, Database } from "lucide-react";
import { nlQuery } from "@/lib/api";
import { useT } from "@/lib/i18n";

const EXAMPLE_QUERIES = [
  "Hvilke 10 selskaper har høyest omsetning?",
  "Vis selskaper med egenkapitalandel under 10%",
  "Hvilke selskaper har negativ egenkapital?",
  "Topp 5 selskaper med høyest risikoscore",
];

export default function NlQueryTab() {
  const T = useT();
  const [question, setQuestion] = useState("");
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState<{ sql: string; columns: string[]; rows: unknown[][]; error: string | null } | null>(null);
  const [err, setErr]           = useState<string | null>(null);

  async function run(q?: string) {
    const q_ = (q ?? question).trim();
    if (!q_) return;
    if (q) setQuestion(q);
    setLoading(true); setErr(null); setResult(null);
    try {
      const r = await nlQuery(q_);
      setResult(r);
      if (r.error) setErr(r.error);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="broker-card space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <Database className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">{T("Naturlig språk til SQL")}</h3>
        </div>
        <p className="text-xs text-muted-foreground">
          {T("Still spørsmål om selskapsdatabasen på norsk — AI oversetter til SQL og returnerer resultatene direkte.")}
        </p>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder={T("F.eks. «Hvilke selskaper har negativ egenkapital?»")}
            className="flex-1 px-3 py-2 text-sm border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <button
            onClick={() => run()}
            disabled={loading || !question.trim()}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
            {T("Kjør")}
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUERIES.map((q) => (
            <button key={q} onClick={() => run(q)}
              className="text-xs px-2.5 py-1 rounded-full bg-muted text-muted-foreground hover:bg-muted transition-colors">
              {T(q)}
            </button>
          ))}
        </div>
      </div>

      {err && (
        <div className="broker-card border-l-4 border-red-400 text-xs text-red-700">
          {err}
        </div>
      )}

      {result && !result.error && result.rows.length === 0 && (
        <div className="broker-card text-sm text-center text-muted-foreground py-6">{T("Ingen resultater.")}</div>
      )}

      {result && result.rows.length > 0 && (
        <div className="broker-card space-y-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <p className="text-xs text-muted-foreground">{result.rows.length} {T("rader")}</p>
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer hover:text-foreground">{T("Vis SQL")}</summary>
              <pre className="mt-2 p-2 bg-primary text-green-300 rounded-lg overflow-x-auto text-xs whitespace-pre-wrap">
                {result.sql}
              </pre>
            </details>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground border-b border-border">
                  {result.columns.map((col) => (
                    <th key={col} className="text-left pb-2 font-medium pr-4">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {result.rows.map((row, i) => (
                  <tr key={i} className="hover:bg-muted">
                    {(row as unknown[]).map((cell, j) => (
                      <td key={j} className="py-2 pr-4 text-foreground">
                        {cell == null ? "–" : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
