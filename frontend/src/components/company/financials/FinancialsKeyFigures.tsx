"use client";

import { useState } from "react";
import { Loader2, Sparkles, Info } from "lucide-react";
import { fmtMnok } from "@/lib/format";
import { getOrgEstimate } from "@/lib/api";

interface Props {
  orgnr: string;
  regn: Record<string, unknown>;
  equityRatio?: number;
  hasHistory: boolean;
  onEstimated?: () => void;
}

const PL_ROWS: Array<[string, string]> = [
  ["Salgsinntekter", "salgsinntekter"],
  ["Sum driftsinntekter", "sum_driftsinntekter"],
  ["Lønnskostnad", "loennskostnad"],
  ["Sum driftskostnad", "sum_driftskostnad"],
  ["Driftsresultat", "driftsresultat"],
  ["Finansinntekter", "sum_finansinntekt"],
  ["Finanskostnader", "sum_finanskostnad"],
  ["Netto finans", "netto_finans"],
  ["Resultat før skatt", "ordinaert_resultat_foer_skattekostnad"],
  ["Skattekostnad", "ordinaert_resultat_skattekostnad"],
  ["Årsresultat", "aarsresultat"],
  ["Totalresultat", "totalresultat"],
];

const BALANCE_ROWS: Array<[string, string]> = [
  ["Sum eiendeler", "sum_eiendeler"],
  ["Omløpsmidler", "sum_omloepsmidler"],
  ["Anleggsmidler", "sum_anleggsmidler"],
  ["Varer", "sum_varer"],
  ["Fordringer", "sum_fordringer"],
  ["Investeringer", "sum_investeringer"],
  ["Bankinnskudd og kontanter", "sum_bankinnskudd_og_kontanter"],
  ["Goodwill", "goodwill"],
  ["Egenkapital", "sum_egenkapital"],
  ["Innskutt egenkapital", "sum_innskutt_egenkapital"],
  ["Opptjent egenkapital", "sum_opptjent_egenkapital"],
  ["Sum gjeld", "sum_gjeld"],
  ["Kortsiktig gjeld", "sum_kortsiktig_gjeld"],
  ["Langsiktig gjeld", "sum_langsiktig_gjeld"],
];

function num(regn: Record<string, unknown>, key: string): number | null {
  const v = regn[key];
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function DetailTable({ title, rows, regn }: { title: string; rows: Array<[string, string]>; regn: Record<string, unknown> }) {
  const present = rows.filter(([, k]) => num(regn, k) != null);
  if (present.length === 0) return null;
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-foreground">{title}</h4>
      <table className="w-full text-xs">
        <tbody>
          {present.map(([label, key]) => (
            <tr key={key} className="border-b border-border last:border-0">
              <td className="py-1.5 text-muted-foreground">{label}</td>
              <td className="py-1.5 text-right font-medium text-foreground">{fmtMnok(num(regn, key))}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[10px] text-muted-foreground">Kilde: BRREG</p>
    </div>
  );
}

export default function FinancialsKeyFigures({ orgnr, regn, equityRatio, hasHistory, onEstimated }: Props) {
  const [estLoading, setEstLoading] = useState(false);
  const [estErr, setEstErr] = useState<string | null>(null);
  const [estDone, setEstDone] = useState(false);

  const hasReal = regn && regn.regnskapsår != null && !regn.synthetic;
  const hasEstimated = !!(regn && regn.synthetic);
  const hasAny = hasReal || hasEstimated;

  async function handleEstimate() {
    setEstLoading(true);
    setEstErr(null);
    try {
      await getOrgEstimate(orgnr);
      setEstDone(true);
      onEstimated?.();
    } catch (e) {
      setEstErr(String(e));
    } finally {
      setEstLoading(false);
    }
  }

  // ── No public regnskap and no estimate → empty state with action ──
  if (!hasAny) {
    return (
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-foreground">Nøkkeltall</h3>
        <p className="text-xs text-muted-foreground">
          Ingen offentlige regnskap tilgjengelig for dette selskapet.
          {!hasHistory && " Du kan be AI generere estimater basert på bransje og størrelse."}
        </p>
        {!hasHistory && (
          <>
            <button
              onClick={handleEstimate}
              disabled={estLoading || estDone}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              {estLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              {estDone ? "Estimat generert" : "Generer AI-estimat"}
            </button>
            {estErr && <p className="text-xs text-red-600">{estErr}</p>}
            {estDone && (
              <p className="text-xs text-muted-foreground">
                Last inn siden på nytt for å vise estimerte tall.
              </p>
            )}
          </>
        )}
      </div>
    );
  }

  const yearLabel = regn.regnskapsår ?? "estimert";

  return (
    <div className="broker-card space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">
          Nøkkeltall <span className="text-muted-foreground font-normal">({String(yearLabel)})</span>
        </h3>
        {hasEstimated && (
          <span className="text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded-full bg-brand-warning/10 text-brand-warning border border-brand-warning/50">
            AI-estimert
          </span>
        )}
      </div>

      {hasEstimated && (
        <div className="border-l-4 border-brand-warning bg-brand-warning/10 px-3 py-2 rounded-r flex items-start gap-2">
          <Info className="w-3.5 h-3.5 text-brand-warning mt-0.5 flex-shrink-0" />
          <p className="text-xs text-muted-foreground">
            Ingen offentlige regnskap funnet i Regnskapsregisteret.
            Tallene under er AI-genererte estimater basert på bransje og selskapstype — kun veiledende.
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Metric label="Omsetning" value={fmtMnok(num(regn, "sum_driftsinntekter"))} />
        <Metric label="Nettoresultat" value={fmtMnok(num(regn, "aarsresultat"))} />
        <Metric label="Egenkapital" value={fmtMnok(num(regn, "sum_egenkapital"))} />
        <Metric
          label="Egenkapitalandel"
          value={equityRatio == null ? "–" : `${(equityRatio * 100).toFixed(1).replace(".", ",")} %`}
        />
      </div>

      {hasReal && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-border">
          <DetailTable title="Resultatregnskap" rows={PL_ROWS} regn={regn} />
          <DetailTable title="Balanse" rows={BALANCE_ROWS} regn={regn} />
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">{label}</p>
      <p className="text-base font-bold text-foreground">{value}</p>
    </div>
  );
}
