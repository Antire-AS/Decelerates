"use client";

import { useState } from "react";
import useSWR from "swr";
import { getAuditLog } from "@/lib/api";
import { Loader2, RefreshCw, Download } from "lucide-react";
import { downloadCsv } from "@/lib/csv-export";
import { SectionHeader } from "./shared";

export function AuditLogSection() {
  const [limit, setLimit] = useState(50);
  const { data: rows, isLoading, mutate } = useSWR<Record<string, unknown>[]>(
    `audit-${limit}`, () => getAuditLog(limit) as Promise<Record<string, unknown>[]>,
  );

  function handleDownload() {
    if (!rows?.length) return;
    downloadCsv(
      rows.map((r) => ({
        Tidspunkt: String(r.created_at ?? "").slice(0, 19).replace("T", " "),
        Bruker: r.actor_email ?? "–",
        Handling: r.action ?? "–",
        Orgnr: r.orgnr ?? "–",
        Detaljer: r.detail ?? "–",
      })),
      `aktivitetslogg_${new Date().toISOString().slice(0, 10)}.csv`,
    );
  }

  const unique_users  = new Set(rows?.map((r) => r.actor_email).filter(Boolean)).size;
  const unique_orgnrs = new Set(rows?.map((r) => r.orgnr).filter(Boolean)).size;

  return (
    <div className="broker-card">
      <div className="flex items-center justify-between mb-3">
        <SectionHeader title="Aktivitetslogg" subtitle="Hvem har brukt applikasjonen og hvilke handlinger de har utført." />
        <div className="flex items-center gap-2">
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="text-xs border border-[#D4C9B8] rounded px-2 py-1 bg-white focus:outline-none"
          >
            {[10, 25, 50, 100, 200].map((v) => <option key={v} value={v}>{v} rader</option>)}
          </select>
          <button onClick={() => mutate()} className="text-[#8A7F74] hover:text-[#2C3E50]">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {rows && rows.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-3">
          {[
            { label: "Oppføringer", value: rows.length },
            { label: "Unike brukere", value: unique_users },
            { label: "Unike selskaper", value: unique_orgnrs },
          ].map(({ label, value }) => (
            <div key={label} className="bg-[#F9F7F4] rounded-lg p-3">
              <p className="text-xs text-[#8A7F74]">{label}</p>
              <p className="text-xl font-bold text-[#2C3E50]">{value}</p>
            </div>
          ))}
        </div>
      )}

      {isLoading && <Loader2 className="w-5 h-5 animate-spin text-[#4A6FA5]" />}
      {!isLoading && !rows?.length && (
        <p className="text-xs text-[#8A7F74]">Ingen aktivitet registrert ennå.</p>
      )}
      {rows && rows.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#EDE8E3]">
                  {["Tidspunkt", "Bruker", "Handling", "Orgnr", "Detaljer"].map((h) => (
                    <th key={h} className="text-left py-2 pr-3 text-[#8A7F74] font-semibold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EDE8E3]">
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-3 whitespace-nowrap text-[#8A7F74]">
                      {String(r.created_at ?? "").slice(0, 19).replace("T", " ")}
                    </td>
                    <td className="py-2 pr-3 text-[#2C3E50]">{String(r.actor_email ?? "–")}</td>
                    <td className="py-2 pr-3 text-[#2C3E50]">{String(r.action ?? "–")}</td>
                    <td className="py-2 pr-3 text-[#8A7F74]">{String(r.orgnr ?? "–")}</td>
                    <td className="py-2 pr-3 text-[#8A7F74] max-w-xs truncate">{String(r.detail ?? "–")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            onClick={handleDownload}
            className="mt-3 flex items-center gap-1.5 text-xs text-[#4A6FA5] hover:underline"
          >
            <Download className="w-3 h-3" /> Eksporter CSV
          </button>
        </>
      )}
    </div>
  );
}
