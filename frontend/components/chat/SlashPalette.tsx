"use client";

import { useEffect, useMemo, useState } from "react";

export type CommandDef = {
  name: string;
  desc: string;
  usage: string;
  trigger: string;
};

type Props = {
  query: string;
  onPick: (cmd: CommandDef) => void;
  visible: boolean;
};

export function SlashPalette({ query, onPick, visible }: Props) {
  const [commands, setCommands] = useState<CommandDef[]>([]);

  useEffect(() => {
    fetch("/api/chat/commands")
      .then((r) => r.json())
      .then(setCommands)
      .catch(() => setCommands([]));
  }, []);

  const filtered = useMemo(() => {
    const q = query.replace(/^\//, "").toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) => c.name.startsWith(q) || c.desc.toLowerCase().includes(q),
    );
  }, [commands, query]);

  if (!visible || filtered.length === 0) return null;
  return (
    <div className="absolute bottom-full mb-2 left-0 right-0 max-h-72 overflow-y-auto rounded-lg border border-white/15 bg-background shadow-lg z-20">
      {filtered.map((c) => (
        <button
          key={c.name}
          className="w-full text-left px-3 py-2 hover:bg-accent/20 border-b border-white/5 last:border-0"
          onMouseDown={(e) => {
            e.preventDefault();
            onPick(c);
          }}
        >
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-accent">{c.trigger}</span>
            <span className="text-xs opacity-70">{c.desc}</span>
          </div>
          <div className="text-xs opacity-50 font-mono mt-0.5">{c.usage}</div>
        </button>
      ))}
    </div>
  );
}
