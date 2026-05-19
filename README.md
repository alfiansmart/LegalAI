# LegalAI

**LegalAI** adalah platform agentic AI khusus untuk hukum Indonesia —
inspirasi dari [Evonic](https://github.com/anvie/evonic) dengan
penambahan primitif khusus hukum (Pasal, Peraturan, Klausa, Redline,
Citation graph) dan **visual Flow Builder** ala Hermes / Open Claw.

## Apa yang bisa dilakukan?

1. **Riset peraturan** — tanya jawab atas korpus UU / KUHP / KUHPerdata
   / KUHAP / Perpres / PP dengan kutipan tingkat pasal & ayat yang
   terverifikasi.
2. **Draft perjanjian** — generate NDA, kontrak kerja, sewa-menyewa,
   jual-beli, dll. dari template + parameter.
3. **Review kontrak** — flag klausa berisiko, klausa hilang, dan
   ketidakkonsistenan terhadap UU rujukan (PDP, Ketenagakerjaan, OJK).
4. **Build flow** — DAG visual yang merangkai *skill* dan *tool* untuk
   SOP hukum yang berulang (mis. *Draft NDA*, *Tinjau Kontrak Vendor*,
   *Riset Hukum*, *Somasi Pipeline*).

## Arsitektur

Konsep inti (Evonic-inspired + penambahan untuk hukum):

| Konsep | Peran |
|---|---|
| **Agent** | Persona (Advokat / Notaris / Researcher / Awam Helper) |
| **Skill** | Bundled capability (`contract_draft`, `pasal_lookup`, …) |
| **Tool** | Atomic function callable by an agent |
| **Channel** | Web UI, WhatsApp, Telegram |
| **Workplace** | Sandbox eksekusi tool (local / docker / cloud) |
| **Knowledge Base** | Vector store + structured corpus + graph |
| **Flow** | DAG visual yang merangkai skill/tool |
| **Document** | Artefak draft (perjanjian, memo, opini) dengan versi & redline |
| **Citation Graph** | Edge antar peraturan/pasal (refers / amends / repeals) |

### Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Celery, Redis
- **DB**: Postgres 16 + `pgvector`, full-text search Bahasa
- **LLM**: Anthropic Claude (`claude-opus-4-7` untuk draft & review,
  `claude-haiku-4-5-20251001` untuk rerank/intent), prompt caching aktif
- **Embeddings**: `intfloat/multilingual-e5-large`
- **Frontend**: Next.js 15 + TypeScript + Tailwind + shadcn/ui +
  React Flow + TipTap

### Retrieval canggih

Bukan flat-RAG — peraturan Indonesia kompleks (multi-hop, amandemen,
referensi silang). LegalAI menggunakan **Graph RAG** (citation graph +
concept graph), **temporal/point-in-time** retrieval, **RAPTOR**
hierarchical summaries, **ColBERT** late-interaction, **CRAG**
self-correcting retrieval, dan **tiga lapis memory** (episodic /
semantic / procedural ala Mem0 + Letta). Lihat
[`docs/retrieval.md`](docs/retrieval.md) untuk detail.

## Quickstart (dev)

```bash
cp .env.example .env
# isi ANTHROPIC_API_KEY
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m backend.corpus.seed_loader
open http://localhost:3000
```

## Status

Phase 0 — foundation (scaffolding). Lihat
[`/root/.claude/plans/learn-about-https-github-com-anvie-evoni-joyful-dijkstra.md`](.)
untuk peta jalan lengkap.

## Lisensi

TBD (lihat *Open questions* di dokumen plan).
