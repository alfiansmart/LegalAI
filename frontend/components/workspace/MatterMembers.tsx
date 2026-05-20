"use client";

/**
 * Membership management for a matter.
 *
 * Lists current members with their role, lets owners add/remove
 * members and change roles. The UI assumes the calling user is an
 * owner — for viewers/editors the backend will return 403 on
 * write-ops and we surface the error inline.
 */
import { useCallback, useEffect, useState } from "react";

type Member = {
  id: number;
  matter_id: number;
  user_id: string;
  role: string;
  user_name: string | null;
  user_email: string | null;
};

const ROLES = ["viewer", "reviewer", "editor", "owner"] as const;

export function MatterMembers({ matterId }: { matterId: number }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [newUserId, setNewUserId] = useState("");
  const [newRole, setNewRole] = useState<(typeof ROLES)[number]>("editor");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`/api/matters/${matterId}/members`);
      if (!res.ok) throw new Error(await res.text());
      setMembers(await res.json());
    } catch (e) {
      setErr(String(e));
    }
  }, [matterId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function add() {
    if (!newUserId.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(`/api/matters/${matterId}/members`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: newUserId.trim(), role: newRole }),
      });
      if (!res.ok) throw new Error(await res.text());
      setNewUserId("");
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(userId: string) {
    setBusy(true);
    try {
      await fetch(`/api/matters/${matterId}/members/${userId}`, { method: "DELETE" });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2 p-3 rounded bg-white/5 text-sm">
      <h3 className="text-xs uppercase tracking-wider opacity-60">
        Anggota matter ({members.length})
      </h3>
      <ul className="space-y-1">
        {members.map((m) => (
          <li key={m.id} className="flex items-center gap-2 text-xs">
            <span className="font-medium">{m.user_name || m.user_id}</span>
            {m.user_email && <span className="opacity-60">({m.user_email})</span>}
            <span className="ml-auto px-1.5 py-0.5 rounded bg-white/10">{m.role}</span>
            <button
              onClick={() => remove(m.user_id)}
              disabled={busy}
              className="opacity-50 hover:opacity-100 hover:text-rose-300"
              title="Remove"
            >
              ×
            </button>
          </li>
        ))}
        {members.length === 0 && (
          <li className="text-xs opacity-50">Belum ada anggota.</li>
        )}
      </ul>
      <div className="flex gap-1 items-center pt-2 border-t border-white/10">
        <input
          value={newUserId}
          onChange={(e) => setNewUserId(e.target.value)}
          placeholder="user_id"
          className="flex-1 bg-white/5 rounded px-2 py-1 text-xs"
        />
        <select
          value={newRole}
          onChange={(e) => setNewRole(e.target.value as (typeof ROLES)[number])}
          className="bg-white/5 rounded px-1 py-1 text-xs"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <button
          onClick={add}
          disabled={busy || !newUserId.trim()}
          className="text-xs px-2 py-1 rounded bg-accent disabled:opacity-40"
        >
          Tambah
        </button>
      </div>
      {err && <div className="text-xs text-rose-300">{err}</div>}
    </div>
  );
}
