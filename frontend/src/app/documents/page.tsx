"use client";

import { useState } from "react";
import useSWR from "swr";
import { getInsuranceDocuments, type InsuranceDocument } from "@/lib/api";

function fmtDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("nb-NO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export default function DocumentsPage() {
  const [orgnrFilter, setOrgnrFilter] = useState("");
  const [appliedFilter, setAppliedFilter] = useState<string | undefined>(undefined);

  const { data: documents, isLoading } = useSWR<InsuranceDocument[]>(
    ["insurance-documents", appliedFilter],
    () => getInsuranceDocuments(appliedFilter),
  );

  function handleFilter() {
    setAppliedFilter(orgnrFilter.trim() || undefined);
  }

  function handleClear() {
    setOrgnrFilter("");
    setAppliedFilter(undefined);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Dokumenter</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          Forsikringsdokumenter og tilbud lastet opp for kundene
        </p>
      </div>

      {/* Filter bar */}
      <div className="broker-card">
        <p className="text-xs text-[#8A7F74] font-medium mb-2">Filtrer på org.nr</p>
        <div className="flex gap-2">
          <input
            type="text"
            value={orgnrFilter}
            onChange={(e) => setOrgnrFilter(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleFilter()}
            placeholder="F.eks. 984851006"
            className="flex-1 px-3 py-2 text-sm border border-[#EDE8E3] rounded-lg
                       text-[#2C3E50] placeholder-[#C8BEB4] focus:outline-none
                       focus:border-[#2C3E50] transition-colors"
          />
          <button
            onClick={handleFilter}
            className="px-4 py-2 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166] transition-colors"
          >
            Søk
          </button>
          {appliedFilter && (
            <button
              onClick={handleClear}
              className="px-4 py-2 rounded-lg bg-[#EDE8E3] text-[#8A7F74] text-sm font-medium hover:bg-[#DDD8D3] transition-colors"
            >
              Nullstill
            </button>
          )}
        </div>
        {appliedFilter && (
          <p className="text-xs text-[#8A7F74] mt-2">
            Viser dokumenter for org.nr: <strong>{appliedFilter}</strong>
          </p>
        )}
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="broker-card space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-8 rounded animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}

      {/* Documents table */}
      {!isLoading && documents && documents.length > 0 && (
        <div className="broker-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-2 font-medium">Filnavn</th>
                <th className="text-left pb-2 font-medium">Org.nr</th>
                <th className="text-left pb-2 font-medium">Tagger</th>
                <th className="text-right pb-2 font-medium">Dato</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-[#F9F7F4]">
                  <td className="py-2">
                    <span className="font-medium text-[#2C3E50] truncate max-w-[200px] block">
                      {doc.filename}
                    </span>
                  </td>
                  <td className="py-2 text-xs text-[#8A7F74]">{doc.orgnr}</td>
                  <td className="py-2">
                    {doc.tags && doc.tags.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {doc.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-xs px-2 py-0.5 rounded-full bg-[#EDE8E3] text-[#8A7F74]"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-[#8A7F74]">–</span>
                    )}
                  </td>
                  <td className="py-2 text-right text-xs text-[#8A7F74]">
                    {fmtDate(doc.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-[#8A7F74] mt-3">{documents.length} dokument(er) funnet</p>
        </div>
      )}

      {!isLoading && documents && documents.length === 0 && (
        <div className="broker-card text-center py-12">
          <p className="text-sm font-medium text-[#2C3E50]">Ingen dokumenter funnet</p>
          <p className="text-xs text-[#8A7F74] mt-1">
            {appliedFilter
              ? `Ingen dokumenter for org.nr ${appliedFilter}.`
              : "Last opp dokumenter via kundeprofilen."}
          </p>
        </div>
      )}

      {!isLoading && !documents && (
        <div className="broker-card text-center py-12">
          <p className="text-sm text-[#8A7F74]">Kunne ikke laste dokumenter.</p>
        </div>
      )}
    </div>
  );
}
