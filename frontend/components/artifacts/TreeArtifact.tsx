"use client";

import { useState } from "react";

import type { TreeNode } from "./ArtifactRenderer";

function Node({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(depth < 1);
  const hasChildren = node.children && node.children.length > 0;
  return (
    <li className="ml-3">
      <div
        className={`flex items-baseline gap-2 ${hasChildren ? "cursor-pointer" : ""}`}
        onClick={() => hasChildren && setOpen((x) => !x)}
      >
        <span className="opacity-50 text-xs w-3">
          {hasChildren ? (open ? "▾" : "▸") : "•"}
        </span>
        <span className="text-sm">{node.label}</span>
        {node.detail && (
          <span className="text-xs opacity-60">— {node.detail}</span>
        )}
      </div>
      {hasChildren && open && (
        <ul className="border-l border-white/10 mt-1">
          {node.children!.map((c, i) => (
            <Node key={i} node={c} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function TreeArtifact({ data }: { data: { root: TreeNode } }) {
  return (
    <ul className="text-sm">
      <Node node={data.root} depth={0} />
    </ul>
  );
}
