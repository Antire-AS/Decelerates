"use client";

import { useCallback, useEffect, useState } from "react";
import { Sparkles, Plus, Trash2, Loader2, Save } from "lucide-react";
import { useT } from "@/lib/i18n";
import {
  getWhiteboard,
  saveWhiteboard,
  generateWhiteboardAiSummary,
  type WhiteboardItem,
  type WhiteboardOut,
} from "@/lib/api";

/**
 * Per-company focus whiteboard.
 *
 * Brokers collect key facts from other tabs (Oversikt, Økonomi, Forsikring)
 * into one workspace here + freeform notes + an AI sparring summary. One
 * whiteboard per (user, orgnr) — content is auto-saved on blur. AI summary
 * is on-demand via the "Spør AI" button.
 */
export default function WhiteboardTab({
  orgnr,
  orgName,
  suggestedFacts,
}: {
  orgnr: string;
  orgName?: string;
  suggestedFacts?: { label: string; value: string; source_tab: string }[];
}) {
  const T = useT();
  const [items, setItems] = useState<WhiteboardItem[]>([]);
  const [notes, setNotes] = useState("");
  const [aiSummary, setAiSummary] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generatingAi, setGeneratingAi] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newValue, setNewValue] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const wb = await getWhiteboard(orgnr);
        setItems((wb.items as WhiteboardItem[]) ?? []);
        setNotes(wb.notes ?? "");
        setAiSummary(wb.ai_summary ?? "");
      } catch {
        /* first load with empty state is fine */
      } finally {
        setLoading(false);
      }
    })();
  }, [orgnr]);

  const persist = useCallback(
    async (nextItems: WhiteboardItem[], nextNotes: string) => {
      setSaving(true);
      try {
        const wb: WhiteboardOut = await saveWhiteboard(orgnr, {
          items: nextItems,
          notes: nextNotes,
        });
        setAiSummary(wb.ai_summary ?? aiSummary);
      } catch {
        /* best-effort save */
      } finally {
        setSaving(false);
      }
    },
    [orgnr, aiSummary],
  );

  function addItem(label: string, value: string, sourceTab = "Manual") {
    const trimmedLabel = label.trim();
    const trimmedValue = value.trim();
    if (!trimmedLabel || !trimmedValue) return;
    const next: WhiteboardItem[] = [
      ...items,
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        label: trimmedLabel,
        value: trimmedValue,
        source_tab: sourceTab,
      },
    ];
    setItems(next);
    void persist(next, notes);
  }

  function handleAddClick() {
    addItem(newLabel, newValue);
    setNewLabel("");
    setNewValue("");
  }

  function removeItem(id: string) {
    const next = items.filter((i) => i.id !== id);
    setItems(next);
    void persist(next, notes);
  }

  function handleNotesBlur() {
    void persist(items, notes);
  }

  async function handleGenerateAi() {
    setGeneratingAi(true);
    try {
      const res = await generateWhiteboardAiSummary(orgnr);
      setAiSummary(res.ai_summary);
    } catch {
      setAiSummary(T("AI-tjenesten er ikke tilgjengelig akkurat nå. Prøv igjen om et øyeblikk."));
    } finally {
      setGeneratingAi(false);
    }
  }

  if (loading) {
    return (
      <div className="broker-card flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin" /> {T("Laster fokus-whiteboard…")}
      </div>
    );
  }

  const existingLabels = new Set(items.map((i) => i.label));
  const availableSuggestions = (suggestedFacts ?? []).filter(
    (s) => !existingLabels.has(s.label),
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Main column — items + notes */}
      <div className="lg:col-span-2 space-y-4">
        <div className="broker-card space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">
              {T("Fakta om")} {orgName ?? orgnr}
            </h3>
            {saving && (
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Save className="w-3 h-3" /> {T("Lagrer…")}
              </span>
            )}
          </div>

          {items.length === 0 && (
            <p className="text-xs text-muted-foreground">
              {T("Dra eller skriv inn fakta du vil ha samlet på ett sted")}.
            </p>
          )}

          <div className="space-y-2">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-2 bg-muted rounded-lg p-2"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-primary">{item.label}</p>
                  <p className="text-sm text-foreground whitespace-pre-wrap break-words">
                    {item.value}
                  </p>
                  {item.source_tab && (
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {T("Fra")}: {item.source_tab}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => removeItem(item.id)}
                  className="text-muted-foreground hover:text-red-500 p-1"
                  title={T("Fjern")}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>

          {/* Suggestions from other tabs */}
          {availableSuggestions.length > 0 && (
            <div className="pt-2 border-t border-border">
              <p className="text-xs font-medium text-muted-foreground mb-2">
                {T("Foreslåtte fakta fra andre faner")}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {availableSuggestions.map((s) => (
                  <button
                    key={`${s.source_tab}-${s.label}`}
                    type="button"
                    onClick={() => addItem(s.label, s.value, s.source_tab)}
                    className="text-xs px-2 py-1 rounded-full border border-border hover:bg-accent hover:text-accent-foreground flex items-center gap-1"
                  >
                    <Plus className="w-3 h-3" /> {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Freeform add */}
          <div className="pt-2 border-t border-border grid grid-cols-1 sm:grid-cols-[1fr_2fr_auto] gap-2">
            <input
              type="text"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder={T("Etikett")}
              className="px-2 py-1.5 text-sm border border-border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
            />
            <input
              type="text"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddClick()}
              placeholder={T("Verdi")}
              className="px-2 py-1.5 text-sm border border-border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
            />
            <button
              type="button"
              onClick={handleAddClick}
              disabled={!newLabel.trim() || !newValue.trim()}
              className="px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" /> {T("Legg til")}
            </button>
          </div>
        </div>

        <div className="broker-card space-y-2">
          <h3 className="text-sm font-semibold text-foreground">{T("Notater")}</h3>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onBlur={handleNotesBlur}
            placeholder={T(
              "Dine egne tanker og hypoteser om selskapet. Lagres automatisk.",
            )}
            className="w-full min-h-[160px] px-3 py-2 text-sm border border-border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
          />
        </div>
      </div>

      {/* AI sparring sidebar */}
      <aside className="broker-card space-y-3 h-fit lg:sticky lg:top-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-primary" /> {T("AI-sparring")}
          </h3>
          <button
            type="button"
            onClick={handleGenerateAi}
            disabled={generatingAi || (items.length === 0 && !notes.trim())}
            className="text-xs px-2 py-1 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
          >
            {generatingAi ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Sparkles className="w-3 h-3" />
            )}
            {T("Spør AI")}
          </button>
        </div>
        {aiSummary ? (
          <div className="bg-muted rounded-lg p-3 text-xs text-foreground whitespace-pre-wrap leading-relaxed">
            {aiSummary}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            {T(
              "Samle noen fakta og/eller skriv notater. Klikk 'Spør AI' for å få en kort sparring-oppsummering.",
            )}
          </p>
        )}
      </aside>
    </div>
  );
}
