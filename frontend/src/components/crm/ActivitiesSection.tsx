"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getOrgActivities, createActivity, completeActivity, deleteActivity,
  getUsers,
  type ActivityItem,
  type User,
} from "@/lib/api";
import { CheckCircle2, Trash2, Plus, ChevronDown, ChevronUp, Clock, User as UserIcon } from "lucide-react";

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
  // Same-firm user list for the assignment dropdown. SWR caches by key so
  // every Activities section in the app shares one fetch.
  const { data: users = [] } = useSWR<User[]>("firm-users", () => getUsers());
  const [listOpen, setListOpen] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving]     = useState(false);
  const [err, setErr]           = useState<string | null>(null);

  const [atype, setAtype]         = useState("call");
  const [subject, setSubject]     = useState("");
  const [body, setBody]           = useState("");
  const [dueDate, setDueDate]     = useState("");
  const [assignedTo, setAssignedTo] = useState<string>("");

  const userById = new Map(users.map((u) => [u.id, u]));

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
        assigned_to_user_id: assignedTo ? Number(assignedTo) : undefined,
      });
      setSubject(""); setBody(""); setDueDate(""); setAssignedTo(""); setFormOpen(false);
      mutate();
    } catch (e) { setErr(String(e)); }
    finally { setSaving(false); }
  }

  return (
    <div className="space-y-2">
      <div className="broker-card">
        <button onClick={() => setListOpen((o) => !o)}
          className="w-full flex items-center justify-between text-sm font-semibold text-foreground">
          <span>📅 Aktiviteter {activities.length > 0 && `(${activities.length})`}</span>
          {listOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {listOpen && (
          <div className="mt-3">
            {activities.length === 0 ? (
              <p className="text-xs text-muted-foreground">Ingen aktiviteter registrert.</p>
            ) : (
              <div className="divide-y divide-border">
                {activities.map((a) => (
                  <div key={a.id} className="py-2.5 flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className={`text-sm font-semibold ${a.completed ? "text-muted-foreground line-through" : "text-foreground"}`}>
                        {TYPE_ICON[a.activity_type] ?? "📌"} {a.subject}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {[
                          TYPE_LABEL[a.activity_type] ?? a.activity_type,
                          a.created_at.slice(0, 10),
                          a.created_by_email,
                        ].filter(Boolean).join(" · ")}
                      </p>
                      {a.body && <p className="text-xs text-muted-foreground mt-0.5">{a.body}</p>}
                      {a.due_date && !a.completed && (
                        <p className="text-xs text-orange-600 flex items-center gap-1 mt-0.5">
                          <Clock className="w-3 h-3" /> Frist: {a.due_date}
                        </p>
                      )}
                      {a.assigned_to_user_id != null && userById.has(a.assigned_to_user_id) && (
                        <p className="text-xs text-primary flex items-center gap-1 mt-0.5">
                          <UserIcon className="w-3 h-3" />
                          Tildelt: {userById.get(a.assigned_to_user_id)?.name || userById.get(a.assigned_to_user_id)?.email}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {!a.completed && a.activity_type === "task" && (
                        <button onClick={() => handleComplete(a.id)}
                          className="text-muted-foreground hover:text-green-600" title="Merk fullført">
                          <CheckCircle2 className="w-4 h-4" />
                        </button>
                      )}
                      <button onClick={() => handleDelete(a.id)} className="text-muted-foreground hover:text-red-500">
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
          className="w-full flex items-center justify-between text-sm font-semibold text-foreground">
          <span className="flex items-center gap-1.5"><Plus className="w-4 h-4" /> Legg til aktivitet</span>
          {formOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {formOpen && (
          <form onSubmit={handleAdd} className="mt-3 space-y-3">
            {/* Type + Emne stack on phones, sit side-by-side on sm+ */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="label-xs" htmlFor="activity-type">Type</label>
                <select id="activity-type" value={atype} onChange={(e) => setAtype(e.target.value)} className="input-sm w-full">
                  {Object.entries(TYPE_LABEL).map(([v, l]) => (
                    <option key={v} value={v}>{TYPE_ICON[v]} {l}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label-xs" htmlFor="activity-subject">Emne *</label>
                <input id="activity-subject" value={subject} onChange={(e) => setSubject(e.target.value)} required className="input-sm w-full" />
              </div>
            </div>
            <div>
              <label className="label-xs" htmlFor="activity-body">Detaljer</label>
              <textarea id="activity-body" value={body} onChange={(e) => setBody(e.target.value)} rows={2}
                className="w-full px-2 py-1.5 text-xs border border-border rounded-lg bg-card resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="label-xs" htmlFor="activity-due-date">Frist (kun for oppgaver)</label>
                <input id="activity-due-date" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs" htmlFor="activity-assigned-to">Tildelt</label>
                <select id="activity-assigned-to" value={assignedTo} onChange={(e) => setAssignedTo(e.target.value)} className="input-sm w-full">
                  <option value="">— Ingen —</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>{u.name || u.email}</option>
                  ))}
                </select>
              </div>
            </div>
            {err && <p className="text-xs text-red-600">{err}</p>}
            {/* Stack buttons on mobile so the submit target stays full-width and tappable */}
            <div className="flex flex-col sm:flex-row gap-2">
              <button type="submit" disabled={saving}
                className="w-full sm:w-auto px-4 py-2 sm:py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                {saving ? "Lagrer…" : "Legg til aktivitet"}
              </button>
              <button type="button" onClick={() => setFormOpen(false)}
                className="w-full sm:w-auto px-3 py-2 sm:py-1.5 text-xs rounded border border-border text-muted-foreground">Avbryt</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
