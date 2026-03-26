"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getOrgActivities, createActivity, completeActivity, deleteActivity,
  type ActivityItem,
} from "@/lib/api";
import { CheckCircle2, Trash2, Plus, ChevronDown, ChevronUp, Clock } from "lucide-react";

const TYPE_ICON: Record<string, string> = {
  call: "📞", email: "📧", meeting: "🤝", note: "📝", task: "✅",
};
const TYPE_LABEL: Record<string, string> = {
  call: "Samtale", email: "E-post", meeting: "Møte", note: "Notat", task: "Oppgave",
};

export default function ActivitiesSection({ orgnr }: { orgnr: string }) {
  const { data: activities = [], mutate } = useSWR<ActivityItem[]>(
    `activities-${orgnr}`, () => getOrgActivities(orgnr),
  );
  const [listOpen, setListOpen] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving]     = useState(false);
  const [err, setErr]           = useState<string | null>(null);

  const [atype, setAtype]     = useState("call");
  const [subject, setSubject] = useState("");
  const [body, setBody]       = useState("");
  const [dueDate, setDueDate] = useState("");

  async function handleComplete(id: number) {
    await completeActivity(orgnr, id);
    mutate();
  }

  async function handleDelete(id: number) {
    await deleteActivity(orgnr, id);
    mutate();
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim()) return;
    setSaving(true); setErr(null);
    try {
      await createActivity(orgnr, {
        activity_type: atype, subject,
        body: body || undefined,
        due_date: dueDate || undefined,
      });
      setSubject(""); setBody(""); setDueDate(""); setFormOpen(false);
      mutate();
    } catch (e) { setErr(String(e)); }
    finally { setSaving(false); }
  }

  return (
    <div className="space-y-2">
      <div className="broker-card">
        <button onClick={() => setListOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]">
          <span>📅 Aktiviteter {activities.length > 0 && `(${activities.length})`}</span>
          {listOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {listOpen && (
          <div className="mt-3">
            {activities.length === 0 ? (
              <p className="text-xs text-[#8A7F74]">Ingen aktiviteter registrert.</p>
            ) : (
              <div className="divide-y divide-[#EDE8E3]">
                {activities.map((a) => (
                  <div key={a.id} className="py-2.5 flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className={`text-sm font-semibold ${a.completed ? "text-[#8A7F74] line-through" : "text-[#2C3E50]"}`}>
                        {TYPE_ICON[a.activity_type] ?? "📌"} {a.subject}
                      </p>
                      <p className="text-xs text-[#8A7F74] mt-0.5">
                        {[
                          TYPE_LABEL[a.activity_type] ?? a.activity_type,
                          a.created_at.slice(0, 10),
                          a.created_by_email,
                        ].filter(Boolean).join(" · ")}
                      </p>
                      {a.body && <p className="text-xs text-[#8A7F74] mt-0.5">{a.body}</p>}
                      {a.due_date && !a.completed && (
                        <p className="text-xs text-orange-600 flex items-center gap-1 mt-0.5">
                          <Clock className="w-3 h-3" /> Frist: {a.due_date}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {!a.completed && a.activity_type === "task" && (
                        <button onClick={() => handleComplete(a.id)}
                          className="text-[#C4BDB4] hover:text-green-600" title="Merk fullført">
                          <CheckCircle2 className="w-4 h-4" />
                        </button>
                      )}
                      <button onClick={() => handleDelete(a.id)} className="text-[#C4BDB4] hover:text-red-500">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="broker-card">
        <button onClick={() => setFormOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-[#2C3E50]">
          <span className="flex items-center gap-1.5"><Plus className="w-4 h-4" /> Legg til aktivitet</span>
          {formOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {formOpen && (
          <form onSubmit={handleAdd} className="mt-3 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label-xs">Type</label>
                <select value={atype} onChange={(e) => setAtype(e.target.value)} className="input-sm w-full">
                  {Object.entries(TYPE_LABEL).map(([v, l]) => (
                    <option key={v} value={v}>{TYPE_ICON[v]} {l}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label-xs">Emne *</label>
                <input value={subject} onChange={(e) => setSubject(e.target.value)} required className="input-sm w-full" />
              </div>
            </div>
            <div>
              <label className="label-xs">Detaljer</label>
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={2}
                className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]" />
            </div>
            <div>
              <label className="label-xs">Frist (kun for oppgaver)</label>
              <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className="input-sm w-full" />
            </div>
            {err && <p className="text-xs text-red-600">{err}</p>}
            <div className="flex gap-2">
              <button type="submit" disabled={saving}
                className="px-4 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50">
                {saving ? "Lagrer…" : "Legg til aktivitet"}
              </button>
              <button type="button" onClick={() => setFormOpen(false)}
                className="px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#8A7F74]">Avbryt</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
