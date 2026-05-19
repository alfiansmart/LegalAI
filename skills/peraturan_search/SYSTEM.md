# Skill: Peraturan Search

Gunakan `peraturan_search` untuk mencari pasal/ayat yang relevan dengan
pertanyaan pengguna. Hasil dikembalikan dalam urutan skor (gabungan
BM25 + cosine + graph expansion).

Petunjuk:
- Ketika pengguna menyebut tahun/peristiwa spesifik, sertakan `as_of`
  agar retrieval menghormati timeline amandemen.
- Sebelum mengutip pasal, panggil `pasal_lookup` untuk mengambil teks
  lengkap dan memverifikasi sebelum dimasukkan ke jawaban.
