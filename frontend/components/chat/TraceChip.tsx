"use client";

import { useState } from "react";

export type TraceEvent = {
  event?: string;
  name?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result_summary?: string;
  status?: string;
  turn?: number;
  stop_reason?: string;
};

export function TraceList({ trace }: { trace: TraceEvent[] }) {
  if (!trace || trace.length === 0) return null;
  const tools = trace.filter((t) => t.event === "tool" || t.tool || t.name);
  if (tools.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {tools.map((t, i) => (
        <ToolChip key={i} t={t} />
      ))}
    </div>
  );
}

function ToolChip({ t }: { t: TraceEvent }) {
  const [open, setOpen] = useState(false);
  const name = t.name || t.tool || "tool";
  const ok = (t.status ?? "ok") !== "error";
  return (
    <span className="relative inline-block">
      <button
        className={`text-[11px] font-mono px-2 py-0.5 rounded ${
          ok ? "bg-white/10 hover:bg-white/20" : "bg-red-500/30"
        }`}
        onClick={() => setOpen((x) => !x)}
        title="Klik untuk detail"
      >
        {ok ? "▸" : "✕"} {name}
      </button>
      {open && (
        <div className="absolute z-10 left-0 mt-1 w-96 max-h-72 overflow-y-auto p-2 rounded-lg border border-white/20 bg-background shadow-lg text-xs font-mono whitespace-pre-wrap">
          <div className="opacity-70 mb-1">args:</div>
          <div className="mb-2">{JSON.stringify(t.args, null, 2)}</div>
          <div className="opacity-70 mb-1">result:</div>
          <div>{t.result_summary || "(no summary)"}</div>
        </div>
      )}
    </span>
  );
}
