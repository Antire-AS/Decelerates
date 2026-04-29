"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Plus, Loader2, Trash2, ArrowRight } from "lucide-react";
import {
  getDeals,
  getPipelineStages,
  moveDealStage,
  deleteDeal,
  getOrgProfile,
  type DealOut,
  type PipelineStageOut,
} from "@/lib/api";
import { NewDealModal } from "@/components/pipeline/NewDealModal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useT } from "@/lib/i18n";

/**
 * Pipeline page — renewal-style tracker.
 *
 * The original /pipeline was a kanban with drag-and-drop (plan §🟢 #9) but
 * broker feedback (2026-04-20) preferred the renewal-style one-row-per-deal
 * + explicit "advance stage" button. This rewrite adopts that pattern and
 * retires drag-drop, which also closes issue #109 (keyboard-a11y drag) by
 * removing the drag surface entirely.
 *
 * Backend contract unchanged: PATCH /deals/{id}/stage + DELETE /deals/{id}.
 */

// Mockup 135146: per-stage probability used to compute "Vektet verdi" header
// metric and the per-row progress bar. Derived from stage `kind` enum so the
// broker doesn't have to enter it per deal. If product wants per-deal override
// later, add an optional `probability` column to the deals table.
const STAGE_PROBABILITY: Record<string, number> = {
  lead: 0.10,
  qualified: 0.25,
  quoted: 0.50,
  bound: 0.75,
  won: 1.00,
  lost: 0.00,
};

function formatNok(n: number): string {
  if (n === 0) return "0 kr";
  if (n >= 1_000_000) return `kr ${(n / 1_000_000).toFixed(1)} mill`;
  if (n >= 1_000) return `kr ${(n / 1_000).toFixed(0)}k`;
  return `kr ${n.toLocaleString("no-NO")}`;
}

export default function PipelinePage() {
  const T = useT();
  const { data: stages = [], error: stagesErr, isLoading: stagesLoading } = useSWR<
    PipelineStageOut[]
  >("pipeline-stages", () => getPipelineStages());
  const { data: deals = [], mutate: mutateDeals, isLoading: dealsLoading } =
    useSWR<DealOut[]>("deals", () => getDeals());

  const [stageFilter, setStageFilter] = useState<number | "all">("all");
  const [advancing, setAdvancing] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalStageId, setModalStageId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DealOut | null>(null);

  // Lazy company-name lookup (same pattern as the previous kanban).
  const [companyNames, setCompanyNames] = useState<Record<string, string>>({});
  useEffect(() => {
    const missing = Array.from(
      new Set(deals.map((d) => d.orgnr).filter((o) => !(o in companyNames))),
    );
    if (missing.length === 0) return;
    let cancelled = false;
    (async () => {
      const updates: Record<string, string> = {};
      await Promise.all(
        missing.map(async (orgnr) => {
          try {
            const prof = await getOrgProfile(orgnr);
            const navn = (prof.org as Record<string, unknown>)?.navn;
            if (typeof navn === "string") updates[orgnr] = navn;
          } catch {
            /* best-effort */
          }
        }),
      );
      if (!cancelled && Object.keys(updates).length > 0) {
        setCompanyNames((prev) => ({ ...prev, ...updates }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [deals, companyNames]);

  async function handleAdvance(deal: DealOut, newStageId: number) {
    setAdvancing(deal.id);
    try {
      await moveDealStage(deal.id, newStageId);
      await mutateDeals();
    } catch (e) {
      console.error("Kunne ikke flytte deal:", e);
    } finally {
      setAdvancing(null);
    }
  }

  async function performDelete(d: DealOut) {
    try {
      await deleteDeal(d.id);
      await mutateDeals();
    } catch (e) {
      console.error("Kunne ikke slette deal:", e);
    }
  }

  const stageCounts = useMemo(
    () =>
      stages.map((s) => ({
        ...s,
        count: deals.filter((d) => d.stage_id === s.id).length,
      })),
    [stages, deals],
  );

  const probabilityFor = (stageId: number): number => {
    const s = stages.find((st) => st.id === stageId);
    return s ? (STAGE_PROBABILITY[s.kind] ?? 0) : 0;
  };

  const { totalValue, weightedValue } = useMemo(() => {
    let total = 0;
    let weighted = 0;
    for (const d of deals) {
      const stage = stages.find((s) => s.id === d.stage_id);
      if (!stage || stage.kind === "lost") continue;
      const v = d.expected_premium_nok ?? 0;
      total += v;
      weighted += v * (STAGE_PROBABILITY[stage.kind] ?? 0);
    }
    return { totalValue: total, weightedValue: weighted };
  }, [deals, stages]);

  const filteredDeals =
    stageFilter === "all" ? deals : deals.filter((d) => d.stage_id === stageFilter);

  const isLoading = stagesLoading || dealsLoading;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{T("Pipeline")}</h1>
          {deals.length > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              {deals.length} {T("saker")} · {T("samlet pipeline-verdi")} {formatNok(totalValue)}
              {totalValue > 0 && (
                <>
                  {" · "}
                  {T("forventet konverteringsrate")} {Math.round((weightedValue / totalValue) * 100)}%
                </>
              )}
            </p>
          )}
        </div>
        <button
          onClick={() => {
            setModalStageId(stages[0]?.id ?? null);
            setModalOpen(true);
          }}
          disabled={stages.length === 0}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Plus className="w-3.5 h-3.5" /> {T("Ny deal")}
        </button>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> {T("Laster pipeline…")}
        </div>
      )}

      {stagesErr && (
        <p className="text-sm text-red-600">{T("Kunne ikke laste pipeline. Sjekk at API-en kjører.")}</p>
      )}

      {!isLoading && stages.length === 0 && (
        <div className="broker-card">
          <p className="text-sm text-muted-foreground">
            {T("Ingen pipeline-stages konfigurert for ditt firma. Standard stages opprettes automatisk via Alembic-migrasjonen — kontakt en admin hvis denne meldingen vises i prod.")}
          </p>
        </div>
      )}

      {/* Pipeline header metrics — total value + probability-weighted value */}
      {stages.length > 0 && deals.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div className="broker-card">
            <p className="text-xs text-muted-foreground">{T("Samlet verdi")}</p>
            <p className="text-2xl font-bold text-foreground mt-0.5">{formatNok(totalValue)}</p>
            <p className="text-xs text-muted-foreground mt-1">{T("Sum forventet årlig premie (eksklusiv tapt)")}</p>
          </div>
          <div className="broker-card">
            <p className="text-xs text-muted-foreground">{T("Vektet verdi")}</p>
            <p className="text-2xl font-bold text-foreground mt-0.5">{formatNok(weightedValue)}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {T("Sannsynlighetsvektet — etter steg-stadium")}
            </p>
          </div>
        </div>
      )}

      {/* Stage summary cards — click to filter */}
      {stages.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          <button
            onClick={() => setStageFilter("all")}
            className={`broker-card text-left transition-all ${
              stageFilter === "all" ? "ring-2 ring-ring" : ""
            }`}
          >
            <p className="text-xs text-muted-foreground">{T("Alle")}</p>
            <p className="text-xl font-bold text-foreground">{deals.length}</p>
          </button>
          {stageCounts.map((s) => (
            <button
              key={s.id}
              onClick={() => setStageFilter(stageFilter === s.id ? "all" : s.id)}
              className={`broker-card text-left transition-all ${
                stageFilter === s.id ? "ring-2 ring-ring" : ""
              }`}
            >
              <p className="text-xs text-muted-foreground">{s.name}</p>
              <p className="text-xl font-bold text-foreground">{s.count}</p>
            </button>
          ))}
        </div>
      )}

      {/* Deal table */}
      {stages.length > 0 && (
        <div className="broker-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">
                  {T("Selskap")}
                </th>
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">
                  {T("Tittel")}
                </th>
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">
                  {T("Steg")}
                </th>
                <th className="text-right py-2 pr-3 text-muted-foreground font-semibold w-32">
                  {T("Verdi")}
                </th>
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold">
                  {T("Flytt til")}
                </th>
                <th className="text-left py-2 pr-3 text-muted-foreground font-semibold w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredDeals.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-muted-foreground">
                    {T("Ingen deals i dette steget.")}
                  </td>
                </tr>
              )}
              {filteredDeals.map((d) => {
                const currentStage = stages.find((s) => s.id === d.stage_id);
                const nextStages = stages.filter((s) => s.id !== d.stage_id);
                const name = companyNames[d.orgnr] ?? d.orgnr;
                return (
                  <tr key={d.id}>
                    <td className="py-2 pr-3">
                      <Link
                        href={`/search/${d.orgnr}`}
                        className="text-primary hover:underline"
                      >
                        {name}
                      </Link>
                    </td>
                    <td className="py-2 pr-3 text-foreground">
                      {d.title ?? T("(uten tittel)")}
                    </td>
                    <td className="py-2 pr-3">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        {currentStage?.name ?? T("Ukjent")}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right">
                      {d.expected_premium_nok != null && d.expected_premium_nok > 0 ? (
                        <div className="space-y-1">
                          <span className="text-xs font-semibold text-foreground tabular-nums">
                            {formatNok(d.expected_premium_nok)}
                          </span>
                          {/* Probability bar — derived from stage kind */}
                          <div className="h-1 bg-muted rounded-full overflow-hidden" title={`${Math.round(probabilityFor(d.stage_id) * 100)}% sannsynlighet`}>
                            <div
                              className="h-full bg-primary rounded-full"
                              style={{ width: `${Math.round(probabilityFor(d.stage_id) * 100)}%` }}
                            />
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      <div className="flex flex-wrap gap-1">
                        {nextStages.slice(0, 3).map((s) => (
                          <button
                            key={s.id}
                            onClick={() => handleAdvance(d, s.id)}
                            disabled={advancing === d.id}
                            className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-border hover:bg-muted disabled:opacity-50"
                          >
                            <ArrowRight className="w-3 h-3" /> {s.name}
                          </button>
                        ))}
                      </div>
                    </td>
                    <td className="py-2 pr-3">
                      <button
                        onClick={() => setPendingDelete(d)}
                        className="p-1.5 rounded text-muted-foreground hover:bg-muted hover:text-red-500"
                        title={T("Slett")}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {modalOpen && modalStageId != null && (
        <NewDealModal
          stages={stages}
          defaultStageId={modalStageId}
          onClose={() => setModalOpen(false)}
          onCreated={() => {
            mutateDeals();
          }}
        />
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(o) => {
          if (!o) setPendingDelete(null);
        }}
        title={
          pendingDelete
            ? `${T("Slett deal")} "${pendingDelete.title ?? pendingDelete.orgnr}"?`
            : ""
        }
        description={T("Handlingen kan ikke angres.")}
        confirmLabel={T("Slett")}
        destructive
        onConfirm={() => {
          if (pendingDelete) performDelete(pendingDelete);
        }}
      />
    </div>
  );
}
