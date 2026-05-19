"use client";

import { useEffect, useState } from "react";

type FlowDef = { slug: string; name: string; description: string };

export default function FlowsPage() {
  const [flows, setFlows] = useState<FlowDef[]>([]);
  useEffect(() => {
    fetch("/api/flows").then((r) => r.json()).then(setFlows).catch(() => setFlows([]));
  }, []);
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Flow Builder</h1>
      <p className="opacity-70 mb-6">
        Flow template siap pakai. Editor visual (React Flow) akan diaktifkan pada Phase 3.
      </p>
      <div className="grid grid-cols-2 gap-4">
        {flows.map((f) => (
          <div key={f.slug} className="p-4 rounded-lg border border-white/10">
            <div className="font-semibold">{f.name}</div>
            <div className="text-sm opacity-70 mt-1">{f.description}</div>
            <div className="text-xs opacity-50 mt-2">slug: {f.slug}</div>
          </div>
        ))}
        {flows.length === 0 && (
          <div className="col-span-2 opacity-60">Belum ada flow tersedia.</div>
        )}
      </div>
    </div>
  );
}
