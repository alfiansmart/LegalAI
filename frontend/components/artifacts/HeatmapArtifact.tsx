"use client";

import type { HeatCell } from "./ArtifactRenderer";

const SEVERITY_COLORS: Record<string, string> = {
  low: "bg-emerald-500/30",
  medium: "bg-amber-500/40",
  high: "bg-orange-500/50",
  critical: "bg-rose-500/60",
};

type HeatmapData = { rows: string[]; cols: string[]; cells: HeatCell[][] };

export function HeatmapArtifact({ data }: { data: HeatmapData }) {
  return (
    <div className="overflow-x-auto">
      <table className="text-xs">
        <thead>
          <tr>
            <th className="px-2 py-1"></th>
            {data.cols.map((c, i) => (
              <th key={i} className="px-2 py-1 font-medium opacity-70">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r, i) => (
            <tr key={i}>
              <th className="px-2 py-1 font-medium opacity-70 text-left whitespace-nowrap">
                {r}
              </th>
              {data.cols.map((_, j) => {
                const cell = data.cells[i]?.[j];
                if (!cell) {
                  return (
                    <td
                      key={j}
                      className="border border-white/5 px-2 py-1 bg-white/0"
                    />
                  );
                }
                const sev = (cell as { severity?: string }).severity || "low";
                const color = SEVERITY_COLORS[sev] || "bg-white/10";
                const label =
                  (cell as { label?: string }).label ??
                  (cell as { value?: number }).value ??
                  "";
                return (
                  <td
                    key={j}
                    title={typeof cell === "object" ? JSON.stringify(cell) : ""}
                    className={`border border-white/5 px-2 py-1 text-center ${color}`}
                  >
                    {String(label)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
