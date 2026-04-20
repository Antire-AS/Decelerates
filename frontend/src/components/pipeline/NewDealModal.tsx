"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Search, X } from "lucide-react";
import {
  searchCompanies,
  createDeal,
  type SearchResult,
  type PipelineStageOut,
  type DealOut,
} from "@/lib/api";

/**
 * Plan §🟢 #9 — "New deal" modal. Inline company autocomplete (debounced)
 * + stage picker + premium estimate. Returns the created DealOut so the
 * parent can optimistically insert it into the kanban without re-fetching.
 */
export function NewDealModal({
  stages,
  defaultStageId,
  onClose,
  onCreated,
}: {
  stages: PipelineStageOut[];
  defaultStageId: number;
  onClose: () => void;
  onCreated: (deal: DealOut) => void;
}) {
  const [companyQuery, setCompanyQuery] = useState("");
  const [companyResults, setCompanyResults] = useState<SearchResult[]>([]);
  const [picked, setPicked] = useState<SearchResult | null>(null);
  const [searching, setSearching] = useState(false);

  const [stageId, setStageId] = useState<number>(defaultStageId);
  const [title, setTitle] = useState("");
  const [premium, setPremium] = useState("");
  const [closeDate, setCloseDate] = useState("");
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");

  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // Debounced company search. Aborts in-flight when the query changes
  // (or when the modal closes) so we don't get stale results racing.
  useEffect(() => {
    if (picked || companyQuery.trim().length < 2) {
      setCompanyResults([]);
      return;
    }
    abortRef.current?.abort();
    const ctl = new AbortController();
    abortRef.current = ctl;
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const r = await searchCompanies(companyQuery.trim(), 8);
        if (!ctl.signal.aborted) setCompanyResults(r);
      } catch {
        // Search failures here are non-fatal — broker can keep typing.
      } finally {
        if (!ctl.signal.aborted) setSearching(false);
      }
    }, 250);
    return () => {
      clearTimeout(t);
      ctl.abort();
    };
  }, [companyQuery, picked]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!picked) {
      setErr("Velg et selskap først.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const deal = await createDeal({
        orgnr: picked.orgnr,
        stage_id: stageId,
        title: title.trim() || null,
        expected_premium_nok: premium ? Number(premium) : null,
        expected_close_date: closeDate || null,
        source: source.trim() || null,
        notes: notes.trim() || null,
      });
      onCreated(deal);
      onClose();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-start sm:items-center justify-center p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-card rounded-lg shadow-xl w-full max-w-lg my-8"
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <h2 className="text-base font-semibold text-foreground">Ny deal</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Company autocomplete */}
          <div>
            <label className="label-xs" htmlFor="new-deal-company-search">Selskap *</label>
            {picked ? (
              <div className="flex items-center justify-between bg-muted border border-border rounded-lg px-3 py-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground truncate">{picked.navn}</p>
                  <p className="text-xs text-muted-foreground">{picked.orgnr}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setPicked(null);
                    setCompanyQuery("");
                  }}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Bytt
                </button>
              </div>
            ) : (
              <>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
                  <input
                    id="new-deal-company-search"
                    autoFocus
                    value={companyQuery}
                    onChange={(e) => setCompanyQuery(e.target.value)}
                    placeholder="Søk etter navn eller orgnr…"
                    className="w-full pl-8 pr-3 py-2 text-sm border border-border rounded-lg
                               bg-card text-foreground placeholder:text-muted-foreground
                               focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </div>
                {searching && (
                  <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" /> Søker…
                  </p>
                )}
                {companyResults.length > 0 && (
                  <div className="mt-1 border border-border rounded-lg max-h-48 overflow-y-auto bg-card">
                    {companyResults.map((r) => (
                      <button
                        type="button"
                        key={r.orgnr}
                        onClick={() => {
                          setPicked(r);
                          setCompanyQuery(r.navn);
                        }}
                        className="w-full text-left px-3 py-2 hover:bg-muted border-b border-border last:border-0"
                      >
                        <p className="text-sm font-medium text-foreground truncate">{r.navn}</p>
                        <p className="text-xs text-muted-foreground">{r.orgnr}</p>
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          <div>
            <label className="label-xs" htmlFor="new-deal-title">Tittel</label>
            <input
              id="new-deal-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="F.eks. Q3 fornyelse"
              className="input-sm w-full"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label-xs" htmlFor="new-deal-stage">Stage *</label>
              <select
                id="new-deal-stage"
                value={stageId}
                onChange={(e) => setStageId(Number(e.target.value))}
                className="input-sm w-full"
              >
                {stages.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label-xs" htmlFor="new-deal-expected-premium">Forventet premie (NOK)</label>
              <input
                id="new-deal-expected-premium"
                type="number"
                value={premium}
                onChange={(e) => setPremium(e.target.value)}
                placeholder="250000"
                className="input-sm w-full"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label-xs" htmlFor="new-deal-close-date">Forventet closing</label>
              <input
                id="new-deal-close-date"
                type="date"
                value={closeDate}
                onChange={(e) => setCloseDate(e.target.value)}
                className="input-sm w-full"
              />
            </div>
            <div>
              <label className="label-xs" htmlFor="new-deal-source">Kilde</label>
              <input
                id="new-deal-source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="Inbound / Referral / …"
                className="input-sm w-full"
              />
            </div>
          </div>

          <div>
            <label className="label-xs" htmlFor="new-deal-notes">Notater</label>
            <textarea
              id="new-deal-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full px-2 py-1.5 text-xs border border-border rounded-lg bg-card resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          {err && <p className="text-xs text-red-600">{err}</p>}

          <div className="flex flex-col sm:flex-row gap-2 pt-2">
            <button
              type="submit"
              disabled={saving || !picked}
              className="w-full sm:w-auto px-4 py-2 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {saving ? "Lagrer…" : "Opprett deal"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="w-full sm:w-auto px-3 py-2 text-xs rounded border border-border text-muted-foreground"
            >
              Avbryt
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
