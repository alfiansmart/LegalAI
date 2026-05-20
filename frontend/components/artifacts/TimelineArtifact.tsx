"use client";

type Event = {
  date?: string;
  year?: number;
  label: string;
  detail?: string;
  kind?: string;
};

const KIND_COLORS: Record<string, string> = {
  amend: "bg-amber-400",
  enact: "bg-emerald-400",
  repeal: "bg-rose-400",
  default: "bg-sky-400",
};

export function TimelineArtifact({ data }: { data: { events: Event[] } }) {
  const events = data.events
    .slice()
    .sort((a, b) => {
      const ax = a.date || (a.year !== undefined ? String(a.year) : "");
      const bx = b.date || (b.year !== undefined ? String(b.year) : "");
      return ax.localeCompare(bx);
    });

  return (
    <ol className="border-l border-white/20 ml-2 space-y-3">
      {events.map((e, i) => {
        const color = KIND_COLORS[e.kind ?? "default"] || KIND_COLORS.default;
        return (
          <li key={i} className="relative pl-4">
            <span
              className={`absolute -left-1.5 top-1 w-3 h-3 rounded-full ${color}`}
            />
            <div className="text-xs opacity-60">{e.date || e.year}</div>
            <div className="text-sm font-medium">{e.label}</div>
            {e.detail && <div className="text-xs opacity-70 mt-0.5">{e.detail}</div>}
          </li>
        );
      })}
      {events.length === 0 && <div className="text-xs opacity-50 pl-4">Tidak ada event.</div>}
    </ol>
  );
}
