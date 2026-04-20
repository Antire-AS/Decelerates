"use client";

import { useState } from "react";
import { getRenewals, getPolicies } from "@/lib/api";
import { Loader2, Download } from "lucide-react";
import { downloadXlsx } from "@/lib/excel-export";
import { SectionHeader, ResultMessage } from "./shared";
import { useT } from "@/lib/i18n";

export function ExportsSection() {
  const T = useT();
  const [loadingRenewals, setLoadingRenewals] = useState(false);
  const [loadingPolicies, setLoadingPolicies] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function handleRenewals() {
    setLoadingRenewals(true); setMsg(null);
    try {
      const data = await getRenewals(365);
      if (!data.length) { setMsg(T("Ingen data funnet.")); return; }
      downloadXlsx(data.map((r) => ({
        Orgnr: r.orgnr, Klient: r.client_name, Forsikringsselskap: r.insurer,
        Produkt: r.insurance_type, "Premie (kr)": r.premium,
        Fornyelsesdato: r.renewal_date, "Dager igjen": r.days_until_renewal, Status: r.status,
      })), `fornyelser_${new Date().toISOString().slice(0, 10)}.xlsx`);
    } catch (e) { setMsg(`${T("Feil")}: ${String(e)}`); }
    finally { setLoadingRenewals(false); }
  }

  async function handlePolicies() {
    setLoadingPolicies(true); setMsg(null);
    try {
      const data = await getPolicies();
      if (!data.length) { setMsg(T("Ingen data funnet.")); return; }
      downloadXlsx(data.map((p) => ({
        Orgnr: p.orgnr, Forsikringsselskap: p.insurer, Produkt: p.product_type ?? "",
        Avtalenr: p.policy_number ?? "", "Premie (kr)": p.annual_premium_nok ?? "",
        "Forsikringssum (kr)": p.coverage_amount_nok ?? "",
        Startdato: p.start_date ?? "", Fornyelsesdato: p.renewal_date ?? "", Status: p.status,
      })), `avtaleoversikt_${new Date().toISOString().slice(0, 10)}.xlsx`);
    } catch (e) { setMsg(`${T("Feil")}: ${String(e)}`); }
    finally { setLoadingPolicies(false); }
  }

  return (
    <div className="broker-card">
      <SectionHeader title={T("Eksporter data")} />
      <div className="flex gap-3 flex-wrap">
        <button
          onClick={handleRenewals}
          disabled={loadingRenewals}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-border text-foreground hover:bg-muted disabled:opacity-50"
        >
          {loadingRenewals ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
          {T("Fornyelsesrapport (Excel)")}
        </button>
        <button
          onClick={handlePolicies}
          disabled={loadingPolicies}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-border text-foreground hover:bg-muted disabled:opacity-50"
        >
          {loadingPolicies ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
          {T("Avtaleoversikt (Excel)")}
        </button>
      </div>
      <ResultMessage msg={msg} />
    </div>
  );
}
