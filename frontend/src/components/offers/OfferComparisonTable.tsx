"use client";

import { Check, Equal } from "lucide-react";
import type { DocumentCompareOut } from "@/lib/api";

/**
 * Side-by-side renderer for the LLM compare output. Plan §🟢 #15.
 *
 * The structured payload coming from POST /insurance-documents/compare is:
 *   {
 *     doc_a_summary, doc_b_summary,
 *     pros_a[], cons_a[], pros_b[], cons_b[],
 *     comparison: [{area, doc_a, doc_b, winner: "A"|"B"|"Lik"}],
 *     conclusion
 *   }
 * Defined in api/services/documents.py::_build_compare_prompt — keep in sync.
 */

type ComparisonRow = {
  area?: string;
  doc_a?: string;
  doc_b?: string;
  winner?: "A" | "B" | "Lik" | string;
};

type Structured = {
  doc_a_summary?: string;
  doc_b_summary?: string;
  pros_a?: string[];
  cons_a?: string[];
  pros_b?: string[];
  cons_b?: string[];
  comparison?: ComparisonRow[];
  conclusion?: string;
};

export function OfferComparisonTable({ result }: { result: DocumentCompareOut }) {
  const structured = (result.structured ?? {}) as Structured;
  const titleA = result.doc_a?.title ?? "Dokument A";
  const titleB = result.doc_b?.title ?? "Dokument B";
  const rows = Array.isArray(structured.comparison) ? structured.comparison : [];

  // Fallback when the LLM didn't return structured JSON (it returned a raw
  // text blob in `raw_text` instead). Show whatever's available so the broker
  // gets *something* useful even on degraded responses.
  const isStructured =
    rows.length > 0 ||
    structured.doc_a_summary ||
    structured.doc_b_summary ||
    structured.conclusion;

  if (!isStructured) {
    const raw = (structured as Record<string, unknown>).raw_text;
    return (
      <div className="bg-[#F9F7F4] rounded-lg p-3">
        <p className="text-xs text-[#2C3E50] whitespace-pre-wrap">
          {typeof raw === "string" ? raw : JSON.stringify(structured, null, 2)}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Two-column summary header */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <SummaryCard title={titleA} summary={structured.doc_a_summary} pros={structured.pros_a} cons={structured.cons_a} />
        <SummaryCard title={titleB} summary={structured.doc_b_summary} pros={structured.pros_b} cons={structured.cons_b} />
      </div>

      {/* Comparison rows table */}
      {rows.length > 0 && (
        <div className="bg-white border border-[#EDE8E3] rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-[#F9F7F4] border-b border-[#EDE8E3]">
              <tr>
                <th className="text-left p-2 font-semibold text-[#2C3E50] w-1/4">Område</th>
                <th className="text-left p-2 font-semibold text-[#2C3E50]">{titleA}</th>
                <th className="text-left p-2 font-semibold text-[#2C3E50]">{titleB}</th>
                <th className="text-center p-2 font-semibold text-[#2C3E50] w-20">Vinner</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const winnerA = row.winner === "A";
                const winnerB = row.winner === "B";
                const tied = row.winner === "Lik";
                return (
                  <tr key={idx} className="border-t border-[#EDE8E3]">
                    <td className="p-2 font-medium text-[#2C3E50] align-top">{row.area ?? "—"}</td>
                    <td className={`p-2 align-top ${winnerA ? "bg-emerald-50 text-emerald-900" : "text-[#2C3E50]"}`}>
                      {row.doc_a ?? "—"}
                    </td>
                    <td className={`p-2 align-top ${winnerB ? "bg-emerald-50 text-emerald-900" : "text-[#2C3E50]"}`}>
                      {row.doc_b ?? "—"}
                    </td>
                    <td className="p-2 text-center align-top">
                      <WinnerBadge winner={row.winner} winnerA={winnerA} winnerB={winnerB} tied={tied} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Conclusion */}
      {structured.conclusion && (
        <div className="bg-[#F9F7F4] border-l-4 border-[#4A6FA5] rounded p-3">
          <p className="text-xs font-semibold text-[#2C3E50] mb-1">Konklusjon</p>
          <p className="text-xs text-[#2C3E50] whitespace-pre-wrap">{structured.conclusion}</p>
        </div>
      )}
    </div>
  );
}

function SummaryCard({
  title,
  summary,
  pros,
  cons,
}: {
  title: string;
  summary?: string;
  pros?: string[];
  cons?: string[];
}) {
  return (
    <div className="bg-white border border-[#EDE8E3] rounded-lg p-3 space-y-2">
      <p className="text-sm font-semibold text-[#2C3E50] truncate" title={title}>{title}</p>
      {summary && <p className="text-xs text-[#2C3E50]">{summary}</p>}
      {pros && pros.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider font-semibold text-emerald-700 mb-0.5">Fordeler</p>
          <ul className="text-xs text-[#2C3E50] space-y-0.5 list-disc list-inside">
            {pros.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </div>
      )}
      {cons && cons.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider font-semibold text-amber-700 mb-0.5">Ulemper</p>
          <ul className="text-xs text-[#2C3E50] space-y-0.5 list-disc list-inside">
            {cons.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function WinnerBadge({
  winner,
  winnerA,
  winnerB,
  tied,
}: {
  winner?: string;
  winnerA: boolean;
  winnerB: boolean;
  tied: boolean;
}) {
  if (winnerA) {
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-700">
        <Check className="w-3 h-3" /> A
      </span>
    );
  }
  if (winnerB) {
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-700">
        <Check className="w-3 h-3" /> B
      </span>
    );
  }
  if (tied) {
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600">
        <Equal className="w-3 h-3" /> Lik
      </span>
    );
  }
  return <span className="text-[10px] text-[#8A7F74]">{winner ?? "—"}</span>;
}
