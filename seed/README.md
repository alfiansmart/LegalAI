# Seed Corpus

Each JSON file represents one peraturan with a small subset of pasal
for Phase-0 scaffolding. Format:

```jsonc
{
  "jenis": "UUD|UU|Perppu|PP|Perpres|Permen|Perda|KUHP|KUHPerdata|KUHAP",
  "nomor": "13",          // null untuk UUD/KUHP/KUHPerdata
  "tahun": 2003,
  "judul": "...",
  "tentang": "...",
  "status": "berlaku|dicabut|diubah",
  "penerbit": "...",
  "source_url": "...",
  "pasal": [
    {
      "nomor": "5",
      "teks": "...",      // boleh kosong jika pasal hanya berisi ayat
      "ayat": [
        {
          "nomor": "1",
          "teks": "...",
          "huruf": [
            {"huruf": "a", "teks": "..."}
          ]
        }
      ]
    }
  ]
}
```

Load with:

```bash
docker compose exec backend python -m backend.corpus.seed_loader
```

Full corpus akan diisi oleh scrapers (`backend/corpus/`) pada Phase 4
dari sumber otoritatif (peraturan.bpk.go.id, jdihn.go.id).
