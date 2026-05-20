"use client";

import { useState } from "react";
import { TaskRunner, TaskKind } from "./TaskRunner";

type Props = {
  matterId: number;
  /** When invoked from a doc row, the document_id is pre-filled. */
  documentIds?: number[];
  onComplete?: () => void;
};

const TASKS: { id: TaskKind; emoji: string; label: string; desc: string }[] = [
  { id: "upload", emoji: "📤", label: "Upload", desc: "Tambahkan kontrak / dokumen" },
  { id: "draft", emoji: "✍️", label: "Draft", desc: "Susun perjanjian dari template" },
  { id: "review", emoji: "🔍", label: "Review", desc: "Tinjau risiko klausa" },
  { id: "compare", emoji: "⚖️", label: "Compare", desc: "Bandingkan dengan template" },
  { id: "research", emoji: "📚", label: "Research", desc: "Riset hukum + memo" },
  { id: "summarize", emoji: "📝", label: "Summarize", desc: "Ringkas dokumen panjang" },
  { id: "extract", emoji: "🧾", label: "Extract", desc: "Ekstrak fakta terstruktur" },
];

export function TaskCards({ matterId, documentIds = [], onComplete }: Props) {
  const [active, setActive] = useState<TaskKind | null>(null);

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
        {TASKS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            className="aspect-square flex flex-col items-center justify-center gap-1 rounded-lg border border-white/10 hover:border-accent/60 hover:bg-accent/5 transition p-2 text-center"
            title={t.desc}
          >
            <div className="text-2xl">{t.emoji}</div>
            <div className="text-xs font-medium">{t.label}</div>
            <div className="text-[10px] opacity-50 leading-tight px-1">{t.desc}</div>
          </button>
        ))}
      </div>
      {active && (
        <TaskRunner
          task={active}
          matterId={matterId}
          documentIds={documentIds}
          onClose={() => {
            setActive(null);
            onComplete?.();
          }}
        />
      )}
    </>
  );
}
