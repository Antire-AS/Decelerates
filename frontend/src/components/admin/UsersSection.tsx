"use client";

import { useState } from "react";
import useSWR from "swr";
import { getUsers, updateUserRole, type User } from "@/lib/api";
import { Loader2 } from "lucide-react";
import { SectionHeader, ResultMessage } from "./shared";
import { useT } from "@/lib/i18n";

const ROLES = ["admin", "broker", "viewer"] as const;

export function UsersSection() {
  const T = useT();
  const { data: users, isLoading } = useSWR<User[]>("users", getUsers);
  const [pendingRoles, setPendingRoles] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function handleSave(u: User) {
    const newRole = pendingRoles[u.id] ?? u.role;
    if (newRole === u.role) { setMsg(T("Ingen endring.")); return; }
    setSaving(u.id); setMsg(null);
    try {
      await updateUserRole(u.id, newRole);
      setMsg(`${T("Rolle oppdatert til")} ${newRole}.`);
    } catch (e) { setMsg(`${T("Feil")}: ${String(e)}`); }
    finally { setSaving(null); }
  }

  return (
    <div className="broker-card">
      <SectionHeader
        title={T("Brukere og tilganger")}
        subtitle={users ? `${users.length} ${T("brukere i firmaet")}` : undefined}
      />
      {isLoading && <Loader2 className="w-5 h-5 animate-spin text-primary" />}
      {!isLoading && !users?.length && (
        <p className="text-xs text-muted-foreground">{T("Ingen brukere funnet.")}</p>
      )}
      {users && users.length > 0 && (
        <div className="divide-y divide-border">
          <div className="grid grid-cols-[3fr_4fr_2fr_auto] gap-3 py-2 text-xs font-semibold text-muted-foreground">
            <span>{T("Navn")}</span><span>{T("E-post")}</span><span>{T("Rolle")}</span><span />
          </div>
          {users.map((u) => (
            <div key={u.id} className="grid grid-cols-[3fr_4fr_2fr_auto] gap-3 py-2.5 items-center">
              <span className="text-sm text-foreground">{u.name ?? "–"}</span>
              <span className="text-xs text-muted-foreground">{u.email}</span>
              <select
                value={pendingRoles[u.id] ?? u.role}
                onChange={(e) => setPendingRoles((p) => ({ ...p, [u.id]: e.target.value }))}
                className="text-xs border border-border rounded px-1.5 py-1 bg-card focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <button
                onClick={() => handleSave(u)}
                disabled={saving === u.id}
                className="text-xs px-2.5 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {saving === u.id ? "…" : T("Lagre")}
              </button>
            </div>
          ))}
        </div>
      )}
      <ResultMessage msg={msg} />
    </div>
  );
}
