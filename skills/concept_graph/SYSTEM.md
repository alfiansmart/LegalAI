# Skill: Concept Graph

Pada saat upload, setiap dokumen diekstrak menjadi entitas (pihak,
konsep, istilah, peraturan rujukan, kewajiban) dan relasi antar-entitas
(`party_to`, `obligated_to`, `defined_in`, `references`, …).

Gunakan tool `concept_neighborhood` ketika pengguna:
- bertanya tentang sebuah pihak atau istilah dan ingin tahu *di mana
  saja ia muncul* lintas dokumen,
- meminta pemetaan kewajiban antara dua pihak,
- ingin grafik visual relasi antar-entitas.

Output adalah `graph` artifact yang langsung dirender di frontend.
