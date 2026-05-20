# Skill: Compare with Commentary

Bandingkan dua dokumen atau dokumen vs template baseline. Hasilkan:

1. **Diff hunks** — perubahan baris per baris dengan konteks.
2. **Komentar AI per hunk** dalam Bahasa Indonesia: apa yang berubah,
   *mengapa itu penting*, dan apakah perubahan tersebut memperkuat
   atau memperlemah posisi salah satu pihak.

Frontend menampilkan:
- `diff` artifact: side-by-side dengan anchor komentar pada hunk yang
  relevan.
- `table` artifact: ringkasan hunk (lokasi, jenis perubahan, severity).
