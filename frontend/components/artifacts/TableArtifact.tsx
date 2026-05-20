"use client";

import { useMemo, useState } from "react";

type TableData = { columns: string[]; rows: unknown[][] };

export function TableArtifact({ data }: { data: TableData }) {
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [filter, setFilter] = useState("");

  const rows = useMemo(() => {
    let r = data.rows.slice();
    if (filter) {
      const f = filter.toLowerCase();
      r = r.filter((row) =>
        row.some((cell) => String(cell ?? "").toLowerCase().includes(f))
      );
    }
    if (sortCol !== null) {
      r.sort((a, b) => {
        const av = String(a[sortCol] ?? "");
        const bv = String(b[sortCol] ?? "");
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      });
    }
    return r;
  }, [data.rows, sortCol, sortDir, filter]);

  function exportCsv() {
    const head = data.columns.join(",");
    const body = rows
      .map((row) =>
        row
          .map((cell) => {
            const v = String(cell ?? "");
            return v.includes(",") || v.includes("\"") ? `"${v.replace(/"/g, '""')}"` : v;
          })
          .join(",")
      )
      .join("\n");
    const blob = new Blob([head + "\n" + body], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "table.csv";
    a.click();
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2 items-center text-xs">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter…"
          className="bg-white/5 rounded px-2 py-1 flex-1"
        />
        <button onClick={exportCsv} className="bg-white/10 rounded px-2 py-1">
          Export CSV
        </button>
      </div>
      <div className="overflow-x-auto border border-white/10 rounded">
        <table className="w-full text-sm">
          <thead className="bg-white/5">
            <tr>
              {data.columns.map((c, i) => (
                <th
                  key={i}
                  onClick={() => {
                    if (sortCol === i) {
                      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
                    } else {
                      setSortCol(i);
                      setSortDir("asc");
                    }
                  }}
                  className="text-left px-2 py-1 font-medium cursor-pointer select-none"
                >
                  {c}
                  {sortCol === i && (sortDir === "asc" ? " ▲" : " ▼")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-t border-white/10">
                {row.map((cell, j) => (
                  <td key={j} className="px-2 py-1 align-top">
                    {String(cell ?? "")}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={data.columns.length} className="px-2 py-3 text-center opacity-50">
                  Tidak ada baris.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
