"use client";

import { use } from "react";
import useSWR from "swr";
import { Loader2, Shield, FileText, AlertTriangle, CheckCircle } from "lucide-react";
import { getClientPortalProfile, type ClientPortalProfile } from "@/lib/api";

function fmt(n: number | undefined | null) {
  if (n == null) return "–";
  return new Intl.NumberFormat("nb-NO").format(Math.round(n));
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    open: "bg-amber-100 text-amber-700",
    settled: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
    active: "bg-green-100 text-green-700",
    expired: "bg-[#EDE8E3] text-[#8A7F74]",
    cancelled: "bg-red-100 text-red-700",
  };
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${map[status] ?? "bg-[#EDE8E3] text-[#8A7F74]"}`}>
      {status}
    </span>
  );
}

export default function ClientPortalPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const { data, isLoading, error } = useSWR<ClientPortalProfile>(
    `portal-${token}`,
    () => getClientPortalProfile(token),
  );

  if (isLoading) return (
    <div className="min-h-screen flex items-center justify-center bg-[#F5F1EC]">
      <Loader2 className="w-8 h-8 animate-spin text-[#4A6FA5]" />
    </div>
  );

  if (error || !data) return (
    <div className="min-h-screen flex items-center justify-center bg-[#F5F1EC]">
      <div className="broker-card text-center max-w-sm mx-4">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
        <p className="text-sm font-semibold text-[#2C3E50]">Lenken er ugyldig eller utløpt</p>
        <p className="text-xs text-[#8A7F74] mt-1">
          Kontakt din forsikringsmegler for en ny lenke.
        </p>
      </div>
    </div>
  );

  const expiresDate = new Date(data.expires_at).toLocaleDateString("nb-NO");
  const riskScore = data.risk_score;

  return (
    <div className="min-h-screen bg-[#F5F1EC]">
      {/* Header */}
      <div className="bg-[#2C3E50] text-white px-6 py-5">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center gap-2 mb-1">
            <Shield className="w-4 h-4 text-[#C8A951]" />
            <span className="text-xs text-white/60 uppercase tracking-wide font-medium">Forsikringsportal</span>
          </div>
          <h1 className="text-xl font-bold">{data.navn ?? data.orgnr}</h1>
          <p className="text-sm text-white/60 mt-0.5">
            {data.orgnr}
            {data.kommune && ` · ${data.kommune}`}
            {data.naeringskode1_beskrivelse && ` · ${data.naeringskode1_beskrivelse}`}
          </p>
          <p className="text-xs text-white/40 mt-2">Tilgang gyldig til {expiresDate}</p>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">

        {/* Risk score */}
        {riskScore != null && (
          <div className="broker-card">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-[#2C3E50]">Risikoscore</p>
              <span className={`text-sm font-bold px-3 py-1 rounded-full ${
                riskScore <= 3 ? "bg-green-100 text-green-700"
                : riskScore <= 7 ? "bg-amber-100 text-amber-700"
                : "bg-red-100 text-red-700"
              }`}>
                {riskScore} / 20
              </span>
            </div>
            {(data.risk_reasons ?? []).length > 0 && (
              <ul className="mt-2 space-y-1">
                {data.risk_reasons!.map((r, i) => (
                  <li key={i} className="text-xs text-[#8A7F74] flex gap-2"><span>•</span>{r}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Active policies */}
        {data.policies.length > 0 && (
          <div className="broker-card">
            <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">
              Aktive forsikringer ({data.policies.length})
            </h2>
            <div className="space-y-2">
              {data.policies.map((p, i) => (
                <div key={i} className="flex items-start justify-between text-sm py-2 border-b border-[#EDE8E3] last:border-0">
                  <div>
                    <p className="font-medium text-[#2C3E50]">{p.product_type}</p>
                    <p className="text-xs text-[#8A7F74]">
                      {p.insurer}
                      {p.policy_number && ` · #${p.policy_number}`}
                    </p>
                    {p.renewal_date && (
                      <p className="text-xs text-[#8A7F74]">
                        Fornyes {new Date(p.renewal_date).toLocaleDateString("nb-NO")}
                      </p>
                    )}
                  </div>
                  {p.annual_premium_nok != null && (
                    <span className="text-sm font-semibold text-[#2C3E50]">
                      kr {fmt(p.annual_premium_nok)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Claims */}
        {data.claims.length > 0 && (
          <div className="broker-card">
            <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">Skader</h2>
            <div className="space-y-2">
              {data.claims.map((c, i) => (
                <div key={i} className="flex items-start justify-between text-sm py-1.5 border-b border-[#EDE8E3] last:border-0">
                  <div>
                    <p className="text-[#2C3E50]">{c.description ?? `Skade #${i + 1}`}</p>
                    {c.incident_date && (
                      <p className="text-xs text-[#8A7F74]">
                        {new Date(c.incident_date).toLocaleDateString("nb-NO")}
                        {c.claim_number && ` · #${c.claim_number}`}
                      </p>
                    )}
                  </div>
                  <StatusBadge status={c.status} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Documents */}
        {data.documents.length > 0 && (
          <div className="broker-card">
            <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">Dokumenter</h2>
            <div className="space-y-1.5">
              {data.documents.map((d, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <FileText className="w-3.5 h-3.5 text-[#8A7F74] flex-shrink-0" />
                  <span className="text-[#2C3E50]">{d.title}</span>
                  {d.uploaded_at && (
                    <span className="text-xs text-[#8A7F74] ml-auto">
                      {new Date(d.uploaded_at).toLocaleDateString("nb-NO")}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {data.policies.length === 0 && data.claims.length === 0 && data.documents.length === 0 && (
          <div className="broker-card text-center py-10">
            <CheckCircle className="w-8 h-8 text-[#8A7F74] mx-auto mb-2" />
            <p className="text-sm text-[#8A7F74]">Ingen forsikringer registrert ennå.</p>
          </div>
        )}

        <p className="text-center text-xs text-[#8A7F74] pb-4">
          Visningen er skrivebeskyttet og generert av din forsikringsmegler.
        </p>
      </div>
    </div>
  );
}
