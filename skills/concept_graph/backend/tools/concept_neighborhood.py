"""Return a k-hop neighborhood of a concept label, packaged as a graph artifact."""
from __future__ import annotations


async def execute(agent=None, args: dict | None = None) -> dict:
    from backend.agents import artifacts as A
    from backend.rag.concept_graph import fetch_concept_neighborhood

    args = args or {}
    label = (args.get("label") or "").strip()
    if not label:
        return {"status": "error", "message": "need label"}
    hops = int(args.get("hops", 1))

    graph_data = await fetch_concept_neighborhood(label, hops=hops)
    nodes = graph_data["nodes"]
    edges = graph_data["edges"]

    if not nodes:
        return {
            "status": "ok",
            "nodes": [],
            "edges": [],
            "message": f"Tidak ada entitas '{label}' dalam concept graph.",
        }

    artifacts = [
        A.graph(
            f"Concept neighborhood: {label}",
            nodes=nodes,
            edges=edges,
            caption=f"{len(nodes)} entitas · {len(edges)} relasi · hops={hops}",
        )
    ]
    return {"status": "ok", "nodes": nodes, "edges": edges, "artifacts": artifacts}
