from __future__ import annotations


async def execute(agent=None, args: dict | None = None) -> dict:
    from sqlalchemy import text

    from backend.db.session import session_scope
    from backend.rag.graphrag import expand_citations

    args = args or {}
    seed_id = int(args["pasal_id"])
    hops = int(args.get("hops", 2))
    pasal_ids = await expand_citations([seed_id], hops=hops)

    # Pull labels for the artifact graph.
    labels: dict[int, str] = {}
    edges: list[dict] = []
    if pasal_ids:
        sql_nodes = text(
            """
            SELECT pasal.id, pasal.nomor AS pasal_nomor,
                   p.jenis, p.nomor AS p_nomor, p.tahun
            FROM pasal JOIN peraturan p ON p.id = pasal.peraturan_id
            WHERE pasal.id = ANY(:ids)
            """
        )
        sql_edges = text(
            """
            SELECT src_pasal_id, dst_pasal_id, kind
            FROM citation_edge
            WHERE src_pasal_id = ANY(:ids) OR dst_pasal_id = ANY(:ids)
            """
        )
        async with session_scope() as s:
            for r in (await s.execute(sql_nodes, {"ids": pasal_ids})).all():
                if r.jenis in {"KUHP", "KUHPerdata", "KUHAP", "UUD"}:
                    label = f"{r.jenis} Pasal {r.pasal_nomor}"
                else:
                    label = f"{r.jenis} {r.p_nomor}/{r.tahun} Pasal {r.pasal_nomor}"
                labels[r.id] = label
            for e in (await s.execute(sql_edges, {"ids": pasal_ids})).all():
                if e.src_pasal_id in labels and e.dst_pasal_id in labels:
                    edges.append(
                        {
                            "src": str(e.src_pasal_id),
                            "dst": str(e.dst_pasal_id),
                            "kind": e.kind.value if hasattr(e.kind, "value") else str(e.kind),
                        }
                    )

    nodes = [{"id": str(pid), "label": labels.get(pid, f"Pasal {pid}")} for pid in pasal_ids]

    artifacts: list[dict] = []
    if nodes:
        from backend.agents import artifacts as A
        artifacts.append(
            A.graph(
                f"Citation network ({len(nodes)} pasal, {len(edges)} edge)",
                nodes=nodes,
                edges=edges,
                caption=f"Mulai dari pasal {seed_id}, hops={hops}.",
            )
        )

    return {
        "status": "ok",
        "pasal_ids": pasal_ids,
        "nodes": nodes,
        "edges": edges,
        "artifacts": artifacts,
    }
