"use client";

import useSWR from "swr";
import { ShieldCheck, ShieldAlert, ShieldQuestion, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { getOrgCoverageGap, type CoverageGapItem } from "@/lib/api";
import { fmtNok } from "@/lib/format";

const PRIORITY_COLORS: Record<string, string> = {
  Kritisk:  "text-red-600 bg-red-50 border-red-200",
  Anbefalt: "text-amber-600 bg-amber-50 border-amber-200",
  Vurder:   "text-blue-600 bg-blue-50 border-blue-200",
};

const PRIORITY_DOT: Record<string, string> = {
  Kritisk:  "bg-red-500",
  Anbefalt: "bg-amber-400",
  Vurder:   "bg-blue-400",
};

function GapRow({ item }: { item: CoverageGapItem }) {
  const [open, setOpen] = useState(false);
  const covered = item.status === "covered";

  return (
    <div className={`rounded-lg border p-3 ${covered ? "border-gray-100 bg-white" : "border-red-100 bg-red-50/40"}`}>
      <div className="flex items-center gap-3">
        {/* Status icon */}
        <div className="flex-shrink-0">
          {covered
            ? <ShieldCheck className="w-5 h-5 text-green-500" />
            : <ShieldAlert className="w-5 h-5 text-red-400" />}
        </div>

        {/* Main info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-[#2C3E50]">{item.type}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${PRIORITY_COLORS[item.priority]}`}>
              {item.priority}
            </span>
            {covered && item.actual_insurer && (
              <span className="text-xs text-[#8A7F74]">{item.actual_insurer}</span>
            )}
          </div>

          {/* Coverage amounts */}
          <div className="flex items-center gap-3 mt-0.5 flex-wrap">
            {covered && item.actual_coverage_nok != null && (
              <span className="text-xs text-[#2C3E50]">
                Dekning: {fmtNok(item.actual_coverage_nok)}
              </span>
            )}
            {item.estimated_coverage_nok != null && (
              <span className="text-xs text-[#8A7F74]">
                Anbefalt: {fmtNok(item.estimated_coverage_nok)}
              </span>
            )}
            {item.coverage_note && (
              <span className="text-xs text-amber-600 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                {item.coverage_note}
              </span>
            )}
          </div>
        </div>

        {/* Expand button */}
        <button
          onClick={() => setOpen((v) => !v)}
          className="text-[#8A7F74] hover:text-[#2C3E50] flex-shrink-0"
        >
          {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {open && (
        <div className="mt-2 ml-8 text-xs text-[#8A7F74] leading-relaxed">
          <p>{item.reason}</p>
          {covered && item.actual_policy_number && (
            <p className="mt-1 text-[#2C3E50]">Polisenr: {item.actual_policy_number}</p>
          )}
          {!covered && (
            <p className="mt-1 text-red-600 font-medium">
              Ingen aktiv polise dekker dette behovet.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function CoverageGapSection({ orgnr }: { orgnr: string }) {
  const { data, isLoading } = useSWR(
    `coverage-gap-${orgnr}`,
    () => getOrgCoverageGap(orgnr),
  );
  const [open, setOpen] = useState(true);

  if (isLoading) {
    return (
      <div className="broker-card">
        <div className="flex items-center gap-2 text-sm text-[#8A7F74]">
          <ShieldQuestion className="w-4 h-4 animate-pulse" />
          Analyserer dekningsgap…
        </div>
      </div>
    );
  }

  if (!data || data.total_count === 0) return null;

  const coveragePct = data.total_count > 0
    ? Math.round((data.covered_count / data.total_count) * 100)
    : 0;

  const barColor = coveragePct >= 80 ? "bg-green-500"
    : coveragePct >= 50 ? "bg-amber-400"
    : "bg-red-500";

  return (
    <div className="broker-card">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 text-sm font-semibold text-[#2C3E50]"
        >
          <ShieldCheck className="w-4 h-4 text-[#4A6FA5]" />
          Dekningstatus
          {open ? <ChevronUp className="w-3 h-3 text-[#8A7F74]" /> : <ChevronDown className="w-3 h-3 text-[#8A7F74]" />}
        </button>

        <div className="flex items-center gap-3">
          <span className="text-xs text-[#8A7F74]">
            {data.covered_count}/{data.total_count} dekket
          </span>
          {data.gap_count > 0 && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-red-100 text-red-600">
              {data.gap_count} gap
            </span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full bg-gray-100 rounded-full mb-4">
        <div
          className={`h-1.5 rounded-full transition-all ${barColor}`}
          style={{ width: `${coveragePct}%` }}
        />
      </div>

      {open && (
        <div className="space-y-2">
          {/* Gaps first, then covered */}
          {[
            ...data.items.filter((i) => i.status === "gap"),
            ...data.items.filter((i) => i.status === "covered"),
          ].map((item) => (
            <GapRow key={item.type} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
