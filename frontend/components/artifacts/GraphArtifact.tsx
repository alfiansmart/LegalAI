"use client";

import { useMemo } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { GraphEdge, GraphNode } from "./ArtifactRenderer";

type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] };

const KIND_COLOR: Record<string, string> = {
  pasal: "#60a5fa",
  uu: "#fbbf24",
  amends: "#f59e0b",
  repeals: "#f87171",
  refers: "#94a3b8",
};

export default function GraphArtifact({ data }: { data: GraphData }) {
  const { nodes, edges } = useMemo(() => {
    const radius = Math.max(80, data.nodes.length * 18);
    const nodes: Node[] = data.nodes.map((n, i) => {
      const angle = (i / Math.max(1, data.nodes.length)) * Math.PI * 2;
      return {
        id: n.id,
        position: { x: Math.cos(angle) * radius + radius, y: Math.sin(angle) * radius + radius },
        data: { label: n.label },
        style: {
          background: KIND_COLOR[n.kind ?? "pasal"] || "#60a5fa",
          color: "#0a0a0a",
          fontSize: 11,
          padding: 6,
          borderRadius: 6,
          border: "none",
        },
      };
    });
    const edges: Edge[] = data.edges.map((e, i) => ({
      id: `e${i}`,
      source: e.src,
      target: e.dst,
      label: e.label || e.kind,
      style: { stroke: KIND_COLOR[e.kind ?? "refers"] || "#94a3b8" },
      labelStyle: { fontSize: 10, fill: "#fff" },
    }));
    return { nodes, edges };
  }, [data]);

  return (
    <div style={{ width: "100%", height: 360 }} className="rounded border border-white/10">
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
