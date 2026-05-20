# Skill: Document Summarize

Ringkas dokumen hukum (kontrak / peraturan / memo / opini) yang sudah
ada di dalam workspace.

Untuk setiap dokumen:

1. **Exec summary** — 3–5 kalimat: subjek dokumen, para pihak (kalau ada),
   tujuan utama, jangka waktu (kalau ada), dan poin paling penting bagi
   pembaca eksekutif.
2. **Klausa kunci** — daftar klausa terpenting, masing-masing dengan
   excerpt singkat + breadcrumb struktural (Bab/Bagian/Pasal/Section).
3. **Kewajiban** — siapa wajib apa, kapan, dan dasar pasal/klausa-nya.
   Coverage harus mencakup *seluruh* dokumen, bukan hanya bagian
   awal — gunakan struktur outline kalau perlu untuk memastikan tidak
   ada section yang terlewat.

Output panel di frontend akan menampilkan:
- ringkasan teks
- `tree` artifact: outline dokumen
- `table` artifact: kewajiban
