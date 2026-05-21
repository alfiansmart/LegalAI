"use client";

/**
 * "Revise with AI" affordance for the document editor.
 *
 * Two entry points:
 *   - Whole-document revise: user types an instruction; AI proposes
 *     changes across the doc as Suggestions.
 *   - Insert a new clause: user picks a clause type or describes it;
 *     AI generates the clause and queues it as an insert-style
 *     Suggestion.
 *
 * Range-scoped revise (highlight text → "rewrite this section") is
 * exposed via the imperative `reviseRange()` method on the parent —
 * see DocumentAIPanel for the wiring.
 */
import { useState } from "react";

type Props = {
  documentId: number;
  onQueued?: () => void;
};

export function ReviseWithAI({ documentId, onQueued }: Props) {
  const [mode, setMode] = useState<"revise" | "insert">("revise");
  const [instruction, setInstruction] = useState("");
  const [clauseType, setClauseType] = useState("force_majeure");
  const [afterSection, setAfterSection] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      let res: Response;
      if (mode === "revise") {
        if (!instruction.trim()) throw new Error("Tulis instruksi dulu.");
        res = await fetch("/api/tasks/draft-revise", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            document_id: documentId,
            instruction: instruction.trim(),
          }),
        });
      } else {
        if (!clauseType.trim()) throw new Error("Pilih atau tulis jenis klausa.");
        res = await fetch("/api/tasks/draft-insert-clause", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            document_id: documentId,
            clause_type: clauseType.trim(),
            after_section: afterSection.trim() || null,
          }),
        });
      }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setMsg(
        mode === "revise"
          ? data.message || `${(data.suggestions || []).length} usulan ditambahkan.`
          : `Klausa baru disisipkan sebagai usulan #${data.suggestion_id}.`
      );
      setInstruction("");
      onQueued?.();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <h3 className="text-xs uppercase tracking-wider opacity-60">🪄 Revise dengan AI</h3>
      <div className="flex gap-1 text-xs">
        {(["revise", "insert"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-2 py-1 rounded ${mode === m ? "bg-accent" : "bg-white/5 hover:bg-white/10"}`}
          >
            {m === "revise" ? "Revisi" : "Sisipkan klausa"}
          </button>
        ))}
      </div>
      {mode === "revise" && (
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="Mis. buat pasal pengakhiran lebih ketat, tambahkan denda 5% per bulan keterlambatan"
          rows={3}
          className="w-full bg-white/5 rounded px-2 py-1 text-xs"
        />
      )}
      {mode === "insert" && (
        <div className="space-y-1">
          <input
            value={clauseType}
            onChange={(e) => setClauseType(e.target.value)}
            placeholder="Jenis klausa (mis. force_majeure, data_protection, atau deskripsi bebas)"
            className="w-full bg-white/5 rounded px-2 py-1 text-xs"
          />
          <input
            value={afterSection}
            onChange={(e) => setAfterSection(e.target.value)}
            placeholder="Sisipkan setelah (opsional, mis. 'Pasal 5')"
            className="w-full bg-white/5 rounded px-2 py-1 text-xs"
          />
        </div>
      )}
      <button
        onClick={submit}
        disabled={busy}
        className="w-full text-xs px-2 py-1 rounded bg-accent disabled:opacity-40"
      >
        {busy ? "AI sedang menyusun…" : mode === "revise" ? "Kirim ke AI" : "Buat klausa"}
      </button>
      {msg && <div className="text-xs opacity-70">{msg}</div>}
      {err && <div className="text-xs text-rose-300">{err}</div>}
    </div>
  );
}
