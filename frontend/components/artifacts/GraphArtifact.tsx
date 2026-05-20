"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { GraphEdge, GraphNode } from "./ArtifactRenderer";

type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] };

const KIND_COLOR: Record<string, string> = {
  pasal: "#60a5fa",
  uu: "#fbbf24",
  party: "#a78bfa",
  concept: "#34d399",
  term: "#22d3ee",
  institution: "#f472b6",
  law: "#fbbf24",
  obligation: "#fb7185",
};

const EDGE_COLOR: Record<string, string> = {
  amends: "#f59e0b",
  repeals: "#f87171",
  refers: "#94a3b8",
  party_to: "#a78bfa",
  obligated_to: "#fb7185",
  defined_in: "#34d399",
  references: "#94a3b8",
  governed_by: "#fbbf24",
};

type PasalDetail = {
  id: number;
  nomor: string;
  teks: string;
  peraturan: { label: string; judul: string };
};

export default function GraphArtifact({ data }: { data: GraphData }) {
  const [selected, setSelected] = useState<{
    node: GraphNode;
    pasal?: PasalDetail | null;
    loading?: boolean;
    error?: string | null;
  } | null>(null);

  const { nodes, edges } = useMemo(() => {
    const radius = Math.max(120, data.nodes.length * 22);
    const nodes: Node[] = data.nodes.map((n, i) => {
      const angle = (i / Math.max(1, data.nodes.length)) * Math.PI * 2;
      const color = KIND_COLOR[n.kind ?? "pasal"] || "#60a5fa";
      return {
        id: n.id,
        position: {
          x: Math.cos(angle) * radius + radius,
          y: Math.sin(angle) * radius + radius,
        },
        data: { label: n.label, kind: n.kind, originalId: n.id },
        style: {
          background: color,
          color: "#0a0a0a",
          fontSize: 11,
          padding: 6,
          borderRadius: 6,
          border: "none",
          cursor: "pointer",
        },
      };
    });
    const edges: Edge[] = data.edges.map((e, i) => ({
      id: `e${i}`,
      source: e.src,
      target: e.dst,
      label: e.label || e.kind,
      style: { stroke: EDGE_COLOR[e.kind ?? "refers"] || "#94a3b8" },
      labelStyle: { fontSize: 10, fill: "#fff" },
      labelBgStyle: { fill: "#0a0a0a", opacity: 0.6 },
    }));
    return { nodes, edges };
  }, [data]);

  const onNodeClick: NodeMouseHandler = useCallback(
    async (_e, node) => {
      const original = data.nodes.find((n) => n.id === node.id);
      if (!original) return;

      // Heuristic: nodes from citation_trace have purely numeric ids that
      // map directly to pasal rows. Concept-graph nodes also have numeric
      // ids but their `kind` is party/concept/term/etc., not pasal/law.
      const looksLikePasal =
        /^\d+$/.test(original.id) && (!original.kind || ["pasal", "law"].includes(original.kind));

      if (!looksLikePasal) {
        setSelected({ node: original });
        return;
      }

      setSelected({ node: original, loading: true });
      try {
        const res = await fetch(`/api/corpus/pasal/${original.id}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const detail = (await res.json()) as PasalDetail;
        setSelected({ node: original, pasal: detail });
      } catch (err) {
        setSelected({ node: original, error: String(err) });
      }
    },
    [data.nodes]
  );

  return (
    <div className="space-y-2">
      <div style={{ width: "100%", height: 360 }} className="rounded border border-white/10 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          onNodeClick={onNodeClick}
          nodesDraggable
          nodesConnectable={false}
        >
          <Background gap={16} />
          <Controls />
        </ReactFlow>
      </div>
      {selected && (
        <NodeDetail
          item={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function NodeDetail({
  item,
  onClose,
}: {
  item: {
    node: GraphNode;
    pasal?: PasalDetail | null;
    loading?: boolean;
    error?: string | null;
  };
  onClose: () => void;
}) {
  return (
    <div className="border border-white/10 rounded p-3 bg-white/[0.03] text-sm">
      <div className="flex items-baseline justify-between mb-1">
        <div className="font-medium">{item.node.label}</div>
        <button
          onClick={onClose}
          className="text-xs opacity-60 hover:opacity-100"
          aria-label="Close"
        >
          ×
        </button>
      </div>
      {item.node.kind && (
        <div className="text-xs opacity-50 uppercase tracking-wider mb-1">
          {item.node.kind}
        </div>
      )}
      {item.loading && <div className="text-xs opacity-60">Memuat pasal…</div>}
      {item.error && (
        <div className="text-xs text-rose-300">Gagal memuat: {item.error}</div>
      )}
      {item.pasal && (
        <div className="space-y-1">
          <div className="text-xs opacity-70">
            {item.pasal.peraturan.label} — Pasal {item.pasal.nomor}
          </div>
          <div className="whitespace-pre-wrap text-xs">{item.pasal.teks}</div>
        </div>
      )}
      {!item.loading && !item.pasal && !item.error && (
        <div className="text-xs opacity-50">Klik node lain untuk detail.</div>
      )}
    </div>
  );
}
