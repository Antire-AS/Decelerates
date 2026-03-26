"use client";

import useSWR from "swr";
import { getSlaAgreements, type SlaAgreement } from "@/lib/api";

function fmtDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("nb-NO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export default function SlaPage() {
  const { data: agreements, isLoading } = useSWR<SlaAgreement[]>(
    "sla-agreements",
    getSlaAgreements,
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Avtaler</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          SLA-avtaler og forsikringsavtaler med kunder
        </p>
      </div>

      {/* Placeholder */}
      <div className="broker-card border-l-4 border-[#C8A951]">
        <p className="text-sm font-semibold text-[#2C3E50] mb-1">Full implementasjon kommer</p>
        <p className="text-sm text-[#8A7F74]">
          Avtalefanen vil støtte oppretting av nye SLA-avtaler med automatisk PDF-generering,
          signering via digital signatur, og varsling til kunde ved fornyelse.
        </p>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="broker-card space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-14 rounded animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}

      {/* Agreements list */}
      {!isLoading && agreements && agreements.length > 0 && (
        <div className="broker-card">
          <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">
            Eksisterende avtaler ({agreements.length})
          </h2>
          <ul className="divide-y divide-[#EDE8E3]">
            {agreements.map((a) => (
              <li key={a.id} className="py-3 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[#2C3E50] truncate">
                    {a.client_name || a.client_orgnr}
                  </p>
                  <p className="text-xs text-[#8A7F74]">
                    Org.nr: {a.client_orgnr} &middot; Opprettet: {fmtDate(a.created_at)}
                  </p>
                </div>
                {a.pdf_url ? (
                  <a
                    href={a.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-shrink-0 px-3 py-1.5 rounded-lg bg-[#2C3E50] text-white text-xs font-medium hover:bg-[#3d5166] transition-colors"
                  >
                    Last ned PDF
                  </a>
                ) : (
                  <span className="flex-shrink-0 text-xs text-[#8A7F74]">Ingen PDF</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!isLoading && agreements && agreements.length === 0 && (
        <div className="broker-card text-center py-12">
          <p className="text-sm font-medium text-[#2C3E50]">Ingen avtaler opprettet ennå</p>
          <p className="text-xs text-[#8A7F74] mt-1">
            Gå til en kundeprofil for å opprette en SLA-avtale.
          </p>
        </div>
      )}

      {!isLoading && !agreements && (
        <div className="broker-card text-center py-12">
          <p className="text-sm text-[#8A7F74]">Kunne ikke laste avtaler.</p>
        </div>
      )}
    </div>
  );
}
