"use client";

import { useMemo } from "react";
import { diffLines } from "diff";

type DiffData = {
  base: string;
  head: string;
  annotations?: { line: number; message: string; severity?: string }[];
};

export default function DiffArtifact({ data }: { data: DiffData }) {
  const parts = useMemo(() => diffLines(data.base, data.head), [data.base, data.head]);
  const annByLine: Record<number, string> = {};
  (data.annotations || []).forEach((a) => {
    annByLine[a.line] = a.message;
  });

  let lineNum = 0;
  return (
    <div className="text-xs font-mono overflow-x-auto bg-white/[0.02] rounded border border-white/10">
      {parts.map((p, i) => {
        const bg = p.added ? "bg-emerald-500/15" : p.removed ? "bg-rose-500/15" : "";
        const marker = p.added ? "+" : p.removed ? "-" : " ";
        const lines = p.value.split("\n");
        // Drop the trailing empty string from a final \n.
        if (lines.length && lines[lines.length - 1] === "") lines.pop();
        return (
          <div key={i} className={bg}>
            {lines.map((ln, j) => {
              lineNum += 1;
              const note = annByLine[lineNum];
              return (
                <div key={j} className="flex">
                  <span className="opacity-30 select-none px-2">{marker}</span>
                  <span className="flex-1 whitespace-pre">{ln}</span>
                  {note && (
                    <span className="text-amber-300 px-2" title={note}>
                      💬
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
