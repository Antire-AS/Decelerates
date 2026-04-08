"use client";

import { useState } from "react";
import useSWR from "swr";
import { getUsers, updateUserRole, type User } from "@/lib/api";
import { Loader2 } from "lucide-react";
import { SectionHeader, ResultMessage } from "./shared";

const ROLES = ["admin", "broker", "viewer"] as const;

export function UsersSection() {
  const { data: users, isLoading } = useSWR<User[]>("users", getUsers);
  const [pendingRoles, setPendingRoles] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function handleSave(u: User) {
    const newRole = pendingRoles[u.id] ?? u.role;
    if (newRole === u.role) { setMsg("Ingen endring."); return; }
    setSaving(u.id); setMsg(null);
    try {
      await updateUserRole(u.id, newRole);
      setMsg(`Rolle oppdatert til ${newRole}.`);
    } catch (e) { setMsg(`Feil: ${String(e)}`); }
    finally { setSaving(null); }
  }

  return (
    <div className="broker-card">
      <SectionHeader
        title="Brukere og tilganger"
        subtitle={users ? `${users.length} brukere i firmaet` : undefined}
      />
      {isLoading && <Loader2 className="w-5 h-5 animate-spin text-[#4A6FA5]" />}
      {!isLoading && !users?.length && (
        <p className="text-xs text-[#8A7F74]">Ingen brukere funnet.</p>
      )}
      {users && users.length > 0 && (
        <div className="divide-y divide-[#EDE8E3]">
          <div className="grid grid-cols-[3fr_4fr_2fr_auto] gap-3 py-2 text-xs font-semibold text-[#8A7F74]">
            <span>Navn</span><span>E-post</span><span>Rolle</span><span />
          </div>
          {users.map((u) => (
            <div key={u.id} className="grid grid-cols-[3fr_4fr_2fr_auto] gap-3 py-2.5 items-center">
              <span className="text-sm text-[#2C3E50]">{u.name ?? "–"}</span>
              <span className="text-xs text-[#8A7F74]">{u.email}</span>
              <select
                value={pendingRoles[u.id] ?? u.role}
                onChange={(e) => setPendingRoles((p) => ({ ...p, [u.id]: e.target.value }))}
                className="text-xs border border-[#D4C9B8] rounded px-1.5 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
              >
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <button
                onClick={() => handleSave(u)}
                disabled={saving === u.id}
                className="text-xs px-2.5 py-1 rounded bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50"
              >
                {saving === u.id ? "…" : "Lagre"}
              </button>
            </div>
          ))}
        </div>
      )}
      <ResultMessage msg={msg} />
    </div>
  );
}
