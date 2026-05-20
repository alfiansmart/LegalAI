# Skill: Document Extract

Ekstrak fakta-fakta penting dari dokumen hukum menjadi data terstruktur.

Output JSON yang stabil dan bisa langsung dipakai:

- **parties**: nama lengkap setiap pihak + perannya (Pihak Pertama / Penjual / Klien dst.).
- **dates**: setiap tanggal penting (penandatanganan, mulai berlaku, jatuh tempo) — sertakan label.
- **money**: nominal yang disebut (nilai kontrak, denda, ganti rugi) — sertakan mata uang.
- **obligations**: kewajiban utama tiap pihak.
- **jurisdiction**: hukum yang berlaku + forum penyelesaian sengketa.
- **governing_law**: peraturan / kitab undang-undang rujukan.

Frontend menampilkan setiap kategori sebagai `table` artifact terpisah.
