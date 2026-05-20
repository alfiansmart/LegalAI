# Skill: Agentic Search

Untuk pertanyaan kompleks yang:
- mengandung beberapa sub-isu ("…dan bagaimana dampaknya…"),
- meminta perbandingan ("…vs…"),
- bersifat temporal/perubahan UU ("…setelah UU Cipta Kerja…"),
- atau ketika `peraturan_search` biasa mengembalikan hasil yang tidak meyakinkan,

panggil `agentic_search`. Pencarian ini akan:

1. Memecah pertanyaan menjadi sub-pertanyaan.
2. Untuk tiap sub-pertanyaan, membuat jawaban hipotetis (HyDE) untuk
   meningkatkan recall semantik, lalu menarik passage relevan.
3. Menggabungkan dan me-rerank.
4. Menilai kecukupan evidence (CRAG). Jika kurang, mencoba sekali lagi
   dengan kueri yang diperbaiki sendiri.

Output mencakup `hits`, `subqueries`, `grade.verdict`, dan `trace`. Gunakan
`grade.verdict` untuk memutuskan: "sufficient" → jawab langsung,
"partial" → jawab tapi tandai keterbatasan, "insufficient" → minta info
tambahan dari pengguna.
