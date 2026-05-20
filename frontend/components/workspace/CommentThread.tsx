"use client";

/**
 * Document comment thread — lives in the AI side panel.
 *
 * Keeps it lightweight: list of comments + a simple "add reply" form +
 * resolve toggle. Threaded view is flat-with-indent (parent_id → one
 * level). Range coordinates (range_start/range_end) are surfaced as a
 * line range chip; we don't try to highlight inside TipTap yet.
 */
import { useCallback, useEffect, useState } from "react";

type Comment = {
  id: number;
  document_id: number;
  user_id: string | null;
  user_name: string | null;
  parent_id: number | null;
  range_start: number | null;
  range_end: number | null;
  body: string;
  resolved: boolean;
  created_at: string;
};

export function CommentThread({ documentId }: { documentId: number }) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`/api/documents/${documentId}/comments`);
      if (!res.ok) throw new Error(await res.text());
      setComments(await res.json());
    } catch (e) {
      setErr(String(e));
    }
  }, [documentId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function submit(parentId: number | null = null, bodyOverride?: string) {
    const text = (bodyOverride ?? draft).trim();
    if (!text) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(`/api/documents/${documentId}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: text, parent_id: parentId }),
      });
      if (!res.ok) throw new Error(await res.text());
      if (!bodyOverride) setDraft("");
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function resolve(id: number) {
    await fetch(`/api/comments/${id}/resolve`, { method: "POST" });
    await refresh();
  }

  const top = comments.filter((c) => c.parent_id === null);
  const childrenOf = (id: number) => comments.filter((c) => c.parent_id === id);

  return (
    <div className="space-y-2">
      <h3 className="text-xs uppercase tracking-wider opacity-60">
        💬 Komentar ({comments.length})
      </h3>
      <ul className="space-y-2 max-h-72 overflow-y-auto">
        {top.map((c) => (
          <CommentItem
            key={c.id}
            comment={c}
            replies={childrenOf(c.id)}
            onResolve={() => resolve(c.id)}
            onReply={(text) => submit(c.id, text)}
          />
        ))}
        {top.length === 0 && (
          <li className="text-xs opacity-50">Belum ada komentar.</li>
        )}
      </ul>

      <div className="space-y-1 border-t border-white/10 pt-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Tambah komentar…"
          rows={2}
          className="w-full bg-white/5 rounded px-2 py-1 text-xs"
        />
        <button
          onClick={() => submit(null)}
          disabled={busy || !draft.trim()}
          className="w-full text-xs px-2 py-1 rounded bg-accent disabled:opacity-40"
        >
          {busy ? "Mengirim…" : "Kirim"}
        </button>
        {err && <div className="text-xs text-rose-300">{err}</div>}
      </div>
    </div>
  );
}

function CommentItem({
  comment,
  replies,
  onResolve,
  onReply,
}: {
  comment: Comment;
  replies: Comment[];
  onResolve: () => void;
  onReply: (text: string) => Promise<void> | void;
}) {
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyText, setReplyText] = useState("");
  return (
    <li
      className={`text-xs p-2 rounded border border-white/10 ${
        comment.resolved ? "opacity-50" : ""
      }`}
    >
      <div className="flex items-baseline justify-between mb-1">
        <span className="font-medium">{comment.user_name || "Anon"}</span>
        <span className="opacity-50">{new Date(comment.created_at).toLocaleString("id-ID")}</span>
      </div>
      <div className="whitespace-pre-wrap">{comment.body}</div>
      <div className="mt-1 flex gap-2 text-[10px] opacity-70">
        <button onClick={() => setReplyOpen((x) => !x)}>↳ Reply</button>
        {!comment.resolved && (
          <button onClick={onResolve}>✓ Resolve</button>
        )}
        {comment.resolved && <span>(resolved)</span>}
      </div>
      {replies.length > 0 && (
        <ul className="ml-3 mt-2 space-y-1 border-l border-white/10 pl-2">
          {replies.map((r) => (
            <li key={r.id} className="text-xs">
              <span className="font-medium">{r.user_name || "Anon"}</span>:{" "}
              <span>{r.body}</span>
            </li>
          ))}
        </ul>
      )}
      {replyOpen && (
        <div className="mt-1 space-y-1">
          <textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            rows={2}
            className="w-full bg-white/5 rounded px-1 py-0.5 text-xs"
          />
          <button
            onClick={async () => {
              await onReply(replyText);
              setReplyText("");
              setReplyOpen(false);
            }}
            disabled={!replyText.trim()}
            className="text-[10px] px-2 py-0.5 rounded bg-accent disabled:opacity-40"
          >
            Kirim reply
          </button>
        </div>
      )}
    </li>
  );
}
