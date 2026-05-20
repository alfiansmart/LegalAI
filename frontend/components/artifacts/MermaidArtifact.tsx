"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Renders a Mermaid diagram. The library is loaded lazily via the
 * dynamic import in ArtifactRenderer.tsx, so this file isn't pulled
 * into the initial bundle.
 */
export default function MermaidArtifact({ data }: { data: { source: string } }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "dark",
        });
        const id = "m" + Math.random().toString(36).slice(2);
        const { svg } = await mermaid.render(id, data.source);
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [data.source]);

  if (error) {
    return (
      <div className="text-xs text-red-300">
        Gagal merender diagram: {error}
        <pre className="mt-1 opacity-70">{data.source}</pre>
      </div>
    );
  }

  return <div ref={ref} className="overflow-x-auto" />;
}
