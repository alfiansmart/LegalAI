"use client";

/**
 * SuggestionsPanel — surface AI + human change proposals on a document.
 *
 * Lives in the AI side panel. Each Suggestion is a track-changes-style
 * proposal: a (range_start, range_end) span on the latest version, plus
 * the proposed replacement text. The lawyer accepts / rejects per
 * suggestion; accepting splices the proposal into a new DocumentVersion
 * via the existing /suggestions/{id}/accept endpoint.
 *
 * We refetch after each accept/reject so the editor sees the new version
 * on next reload, and we expose a `onChanged()` callback so the parent
 * can re-fetch the document content to reflect the splice.
 */
import { useCallback, useEffect, useState } from "react";

type Suggestion = {
  id: number;
  document_id: number;
  user_id: string | null;
  source: string;
  range_start: number;
  range_end: number;
  base_text: string;
  proposed_text: string;
  rationale: string | null;
  status: string;
  created_at: string;
};

type Props = {
  documentId: number;
  onChanged?: () => void;
};

export function SuggestionsPanel({ documentId, onChanged }: Props) {
  const [items, setItems] = useState<Suggestion[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`/api/documents/${documentId}/suggestions`);
      if (!res.ok) throw new Error(await res.text());
      setItems(await res.json());
    } catch (e) {
      setErr(String(e));
    }
  }, [documentId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function resolve(id: number, accept: boolean) {
    setBusyId(id);
    setErr(null);
    try {
      const verb = accept ? "accept" : "reject";
      const res = await fetch(`/api/suggestions/${id}/${verb}`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      await refresh();
      if (accept) onChanged?.();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusyId(null);
    }
  }

  const pending = items.filter((s) => s.status === "pending");
  const resolved = items.filter((s) => s.status !== "pending");

  return (
    <div className="space-y-2">
      <h3 className="text-xs uppercase tracking-wider opacity-60">
        🪄 Usulan AI ({pending.length} pending)
      </h3>
      <ul className="space-y-2 max-h-72 overflow-y-auto">
        {pending.map((s) => (
          <SuggestionRow
            key={s.id}
            sug={s}
            busy={busyId === s.id}
            onAccept={() => resolve(s.id, true)}
            onReject={() => resolve(s.id, false)}
          />
        ))}
        {pending.length === 0 && (
          <li className="text-xs opacity-50">Belum ada usulan tertunda.</li>
        )}
      </ul>
      {resolved.length > 0 && (
        <details className="text-xs opacity-70">
          <summary className="cursor-pointer">Riwayat ({resolved.length})</summary>
          <ul className="mt-1 space-y-1">
            {resolved.map((s) => (
              <li key={s.id} className="text-xs">
                <span className="opacity-50">#{s.id}</span> · {s.status} ·{" "}
                {s.rationale?.slice(0, 80) || s.proposed_text.slice(0, 80)}
              </li>
            ))}
          </ul>
        </details>
      )}
      {err && <div className="text-xs text-rose-300">{err}</div>}
    </div>
  );
}

function SuggestionRow({
  sug,
  busy,
  onAccept,
  onReject,
}: {
  sug: Suggestion;
  busy: boolean;
  onAccept: () => void;
  onReject: () => void;
}) {
  const isInsert = sug.range_start === sug.range_end;
  return (
    <li className="text-xs p-2 rounded border border-white/10 space-y-1">
      <div className="flex items-baseline justify-between">
        <span className="font-medium">
          {sug.source === "ai" ? "🤖 AI" : "👤 Manusia"}
        </span>
        <span className="opacity-50">
          {isInsert
            ? `insert @${sug.range_start}`
            : `${sug.range_start}–${sug.range_end}`}
        </span>
      </div>
      {sug.rationale && (
        <div className="opacity-70 italic">{sug.rationale}</div>
      )}
      {!isInsert && sug.base_text && (
        <div className="text-rose-300/80 line-through whitespace-pre-wrap text-[11px]">
          {sug.base_text.length > 200
            ? sug.base_text.slice(0, 200) + "…"
            : sug.base_text}
        </div>
      )}
      <div className="text-emerald-300/90 whitespace-pre-wrap text-[11px]">
        {sug.proposed_text.length > 240
          ? sug.proposed_text.slice(0, 240) + "…"
          : sug.proposed_text}
      </div>
      <div className="flex gap-1 pt-1">
        <button
          onClick={onAccept}
          disabled={busy}
          className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/30 hover:bg-emerald-500/50 disabled:opacity-40"
        >
          {busy ? "…" : "✓ Terima"}
        </button>
        <button
          onClick={onReject}
          disabled={busy}
          className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-rose-500/30 disabled:opacity-40"
        >
          ✗ Tolak
        </button>
      </div>
    </li>
  );
}
