"use client";

/**
 * ArtifactRenderer — dispatch on artifact.type, lazy-load heavy renderers.
 *
 * The agent emits visual artifacts (diagrams, tables, charts, timelines,
 * trees, heatmaps, diffs, citation graphs) alongside its text reply. This
 * component is the single render entry point used by both chat bubbles
 * and task panels.
 *
 * Heavy deps (mermaid, recharts, @xyflow/react) are loaded with `next/dynamic`
 * so they don't enter the initial bundle.
 */
import dynamic from "next/dynamic";
import { useMemo } from "react";

const MermaidArtifact = dynamic(() => import("./MermaidArtifact"), { ssr: false });
const ChartArtifact = dynamic(() => import("./ChartArtifact"), { ssr: false });
const GraphArtifact = dynamic(() => import("./GraphArtifact"), { ssr: false });
const DiffArtifact = dynamic(() => import("./DiffArtifact"), { ssr: false });

import { TableArtifact } from "./TableArtifact";
import { TimelineArtifact } from "./TimelineArtifact";
import { TreeArtifact } from "./TreeArtifact";
import { HeatmapArtifact } from "./HeatmapArtifact";

export type ArtifactType =
  | "mermaid"
  | "table"
  | "chart"
  | "timeline"
  | "tree"
  | "heatmap"
  | "diff"
  | "graph";

export type Artifact = {
  id: string;
  type: ArtifactType;
  title: string;
  caption?: string;
  data: Record<string, unknown>;
};

export function ArtifactRenderer({ artifact }: { artifact: Artifact }) {
  const body = useMemo(() => {
    switch (artifact.type) {
      case "mermaid":
        return <MermaidArtifact data={artifact.data as { source: string }} />;
      case "table":
        return (
          <TableArtifact
            data={artifact.data as { columns: string[]; rows: unknown[][] }}
          />
        );
      case "chart":
        return (
          <ChartArtifact
            data={artifact.data as { kind: string; series: unknown[] }}
          />
        );
      case "timeline":
        return (
          <TimelineArtifact
            data={artifact.data as { events: { date?: string; year?: number; label: string; detail?: string; kind?: string }[] }}
          />
        );
      case "tree":
        return <TreeArtifact data={artifact.data as { root: TreeNode }} />;
      case "heatmap":
        return (
          <HeatmapArtifact
            data={artifact.data as { rows: string[]; cols: string[]; cells: HeatCell[][] }}
          />
        );
      case "diff":
        return (
          <DiffArtifact
            data={artifact.data as { base: string; head: string; annotations?: unknown[] }}
          />
        );
      case "graph":
        return (
          <GraphArtifact
            data={artifact.data as { nodes: GraphNode[]; edges: GraphEdge[] }}
          />
        );
      default:
        return (
          <pre className="text-xs opacity-60">
            Unsupported artifact type: {(artifact as { type: string }).type}
          </pre>
        );
    }
  }, [artifact]);

  return (
    <div className="border border-white/10 rounded-lg p-3 bg-white/5">
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-sm font-medium">{artifact.title}</div>
        <div className="text-xs opacity-50 uppercase tracking-wider">
          {artifact.type}
        </div>
      </div>
      {body}
      {artifact.caption && (
        <div className="text-xs opacity-60 mt-2">{artifact.caption}</div>
      )}
    </div>
  );
}

// ---------- shared types referenced above ----------

export type TreeNode = {
  label: string;
  detail?: string;
  children?: TreeNode[];
};

export type HeatCell = {
  value?: number;
  label?: string;
  severity?: "low" | "medium" | "high" | "critical";
} | null;

export type GraphNode = { id: string; label: string; kind?: string };
export type GraphEdge = { src: string; dst: string; kind?: string; label?: string };
