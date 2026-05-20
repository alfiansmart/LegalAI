"use client";

/**
 * AI side panel that rides alongside the document editor.
 *
 * - Quick actions for the doc (Review / Ringkas / Ekstrak / Bandingkan)
 *   route through the same TaskRunner modal used on the matter page.
 * - An inline Q&A box lets the lawyer ask free-form questions; queries
 *   are answered by the matter-scoped agent (so retrieval expands over
 *   the matter's full doc set, including the one open in the editor).
 */
import { useState } from "react";
import { ArtifactRenderer, type Artifact } from "@/components/artifacts/ArtifactRenderer";
import { PasalChip, type Citation } from "@/components/citation/PasalChip";
import { TaskRunner, type TaskKind } from "./TaskRunner";

type Finding = {
  id?: string;
  severity?: string;
  clause_excerpt?: string;
  recommendation?: string;
};

type Props = {
  documentId: number;
  matterId?: number | null;
};

const QUICK_ACTIONS: { id: TaskKind; emoji: string; label: string }[] = [
  { id: "review", emoji: "🔍", label: "Review risiko" },
  { id: "summarize", emoji: "📝", label: "Ringkas" },
  { id: "extract", emoji: "🧾", label: "Ekstrak fakta" },
  { id: "compare", emoji: "⚖️", label: "Bandingkan" },
];

type QAResponse = {
  reply: string;
  citations: Citation[];
  artifacts: Artifact[];
};

export function DocumentAIPanel({ documentId, matterId }: Props) {
  const [activeTask, setActiveTask] = useState<TaskKind | null>(null);
  const [lastFindings, setLastFindings] = useState<Finding[] | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [qa, setQa] = useState<QAResponse | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  async function ask() {
    const text = question.trim();
    if (!text) return;
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          agent: "reviewer",
          message: `Tanya tentang dokumen #${documentId}: ${text}`,
          matter_id: matterId,
        }),
      });
      const data = await res.json();
      setSessionId(data.session_id);
      setQa({
        reply: data.reply,
        citations: data.citations || [],
        artifacts: data.artifacts || [],
      });
      setQuestion("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="w-80 shrink-0 border-l border-white/10 pl-4 space-y-4">
      <div>
        <h3 className="text-xs uppercase tracking-wider opacity-60 mb-2">
          Quick actions
        </h3>
        <div className="grid grid-cols-2 gap-1">
          {QUICK_ACTIONS.map((a) => (
            <button
              key={a.id}
              onClick={() => setActiveTask(a.id)}
              className="text-xs px-2 py-1 rounded bg-white/5 hover:bg-accent/20 text-left"
            >
              <span>{a.emoji}</span> {a.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-xs uppercase tracking-wider opacity-60 mb-2">
          💬 Tanya tentang dokumen
        </h3>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              ask();
            }
          }}
          rows={3}
          placeholder="Apakah klausa pengakhiran sepihak diperbolehkan?"
          className="w-full bg-white/5 rounded px-2 py-1 text-sm"
        />
        <button
          onClick={ask}
          disabled={busy || !question.trim()}
          className="mt-1 w-full text-xs px-2 py-1 rounded bg-accent disabled:opacity-40"
        >
          {busy ? "Berpikir…" : "Kirim (⌘↩)"}
        </button>
      </div>

      {qa && (
        <div className="space-y-2 border-t border-white/10 pt-3">
          <div className="text-xs opacity-60">Jawaban:</div>
          <div className="text-sm whitespace-pre-wrap">{qa.reply}</div>
          {qa.citations.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {qa.citations.map((c, i) => (
                <PasalChip key={i} c={c} />
              ))}
            </div>
          )}
          {qa.artifacts.length > 0 && (
            <div className="space-y-2">
              {qa.artifacts.map((a) => (
                <ArtifactRenderer key={a.id} artifact={a} />
              ))}
            </div>
          )}
        </div>
      )}

      {lastFindings && lastFindings.length > 0 && (
        <div className="border-t border-white/10 pt-3 space-y-1">
          <h3 className="text-xs uppercase tracking-wider opacity-60 mb-1">
            Findings terakhir
          </h3>
          <ul className="space-y-1">
            {lastFindings.slice(0, 6).map((f, i) => (
              <li
                key={i}
                className="text-xs p-1.5 rounded bg-white/5 flex items-baseline gap-1"
              >
                <span className={severityBadge(f.severity)}>
                  {(f.severity || "low").slice(0, 1).toUpperCase()}
                </span>
                <span className="truncate">{f.clause_excerpt || f.recommendation}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {activeTask && (
        <TaskRunner
          task={activeTask}
          matterId={matterId ?? 0}
          documentIds={[documentId]}
          onClose={() => {
            setActiveTask(null);
            // Refresh findings after a Review run by re-calling the endpoint.
            if (activeTask === "review") {
              fetch("/api/tasks/review", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ document_id: documentId }),
              })
                .then((r) => r.json())
                .then((d) => setLastFindings(d.findings || []))
                .catch(() => {});
            }
          }}
        />
      )}
    </aside>
  );
}

function severityBadge(sev?: string): string {
  switch ((sev || "low").toLowerCase()) {
    case "critical":
      return "px-1 rounded bg-rose-500 text-black font-bold";
    case "high":
      return "px-1 rounded bg-orange-500 text-black font-bold";
    case "medium":
      return "px-1 rounded bg-amber-500 text-black font-bold";
    default:
      return "px-1 rounded bg-emerald-500/60 text-black font-bold";
  }
}
