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

# Seed kitabs (KUHP / KUHPerdata / KUHAP / UUD) + embed otomatis
docker compose exec backend python -m backend.corpus.seed_loader

# (opsional) embed ulang batch
curl -X POST http://localhost:8000/corpus/embed

# Chat
curl -X POST http://localhost:8000/chat \
     -H 'content-type: application/json' \
     -d '{"message":"Apa syarat sah perjanjian menurut KUHPerdata?"}'

open http://localhost:3000
```

## Verifikasi Phase 1 & 2

- **Phase 1**: `GET /corpus/stats` → `peraturan ≥ 4`, `embedded > 0`.
  `POST /search {"q":"syarat sah perjanjian"}` → Pasal 1320 KUHPerdata
  di top-3. Chat: tanya *"Apa syarat sah perjanjian?"* → jawaban
  memuat chip `Pasal 1320 KUHPerdata` (hover untuk preview).
- **Phase 2 — drafting**: chat ke persona `drafter`,
  *"Buat NDA antara PT Alpha dan PT Beta untuk diskusi joint-venture"*
  → tool `contract_draft` membuat Document → muncul di `/documents`.
- **Phase 2 — review**: chat ke persona `reviewer`, paste kontrak →
  `contract_review` mengembalikan findings (severity + pasal anchor).
- **Phase 2 — memo**: persona `researcher` →  `legal_memo_compose` →
  memo terstruktur.
- **Phase 2 — editor & export**: buka `/documents/{id}`, edit di TipTap,
  klik *Export .docx*.

## Status

Phase 2 — drafting & review (live). Lihat
[`/root/.claude/plans/learn-about-https-github-com-anvie-evoni-joyful-dijkstra.md`](.)
untuk peta jalan lengkap.

## Lisensi

TBD (lihat *Open questions* di dokumen plan).
