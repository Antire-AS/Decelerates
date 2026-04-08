"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getOrgBrokerNotes,
  createOrgBrokerNote,
  deleteOrgBrokerNote,
  type BrokerNote,
} from "@/lib/api";
import { Loader2, Trash2, Plus, StickyNote } from "lucide-react";

export default function NotaterSection({ orgnr }: { orgnr: string }) {
  const { data: notes = [], isLoading, mutate } = useSWR<BrokerNote[]>(
    `broker-notes-${orgnr}`,
    () => getOrgBrokerNotes(orgnr),
  );

  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleCreate() {
    const trimmed = text.trim();
    if (!trimmed) return;
    setSaving(true);
    setErr(null);
    try {
      await createOrgBrokerNote(orgnr, trimmed);
      setText("");
      mutate();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    await deleteOrgBrokerNote(orgnr, id);
    mutate();
  }

  return (
    <div className="space-y-4">
      {/* Add note form */}
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
          <StickyNote className="w-4 h-4" />
          Ny notat
        </h3>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Skriv et notat om selskapet…"
          rows={3}
          className="w-full text-sm border border-[#D4C9B8] rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50] placeholder:text-[#C4BDB4]"
        />
        {err && <p className="text-xs text-red-600">{err}</p>}
        <button
          onClick={handleCreate}
          disabled={saving || !text.trim()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
          Lagre notat
        </button>
      </div>

      {/* Notes list */}
      <div className="broker-card space-y-1">
        <h3 className="text-sm font-semibold text-[#2C3E50] mb-2">
          Notater {notes.length > 0 && `(${notes.length})`}
        </h3>
        {isLoading ? (
          <div className="flex items-center gap-2 text-xs text-[#8A7F74]">
            <Loader2 className="w-4 h-4 animate-spin" /> Henter notater…
          </div>
        ) : notes.length === 0 ? (
          <p className="text-xs text-[#8A7F74]">Ingen notater ennå.</p>
        ) : (
          <div className="divide-y divide-[#EDE8E3]">
            {notes.map((n) => (
              <div key={n.id} className="py-3 flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[#2C3E50] whitespace-pre-wrap break-words">{n.text}</p>
                  <p className="text-xs text-[#C4BDB4] mt-1">{n.created_at.slice(0, 10)}</p>
                </div>
                <button
                  onClick={() => handleDelete(n.id)}
                  className="flex-shrink-0 text-[#C4BDB4] hover:text-red-500 mt-0.5"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
