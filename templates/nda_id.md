# PERJANJIAN KERAHASIAAN
## (Non-Disclosure Agreement)

Perjanjian Kerahasiaan ini ("**Perjanjian**") dibuat dan ditandatangani
pada hari {{ tanggal }} oleh dan antara:

1. **{{ disclosing_party.nama }}**, berkedudukan di {{ disclosing_party.alamat }},
   dalam hal ini diwakili oleh {{ disclosing_party.wakil }} selaku
   {{ disclosing_party.jabatan }} (selanjutnya disebut "**Pihak Pengungkap**");

2. **{{ receiving_party.nama }}**, berkedudukan di {{ receiving_party.alamat }},
   dalam hal ini diwakili oleh {{ receiving_party.wakil }} selaku
   {{ receiving_party.jabatan }} (selanjutnya disebut "**Pihak Penerima**").

(Pihak Pengungkap dan Pihak Penerima selanjutnya secara bersama-sama
disebut "**Para Pihak**".)

**MENGINGAT:**
- Bahwa Para Pihak berniat membahas {{ purpose }} ("**Tujuan**");
- Bahwa dalam pembahasan tersebut Pihak Pengungkap dapat mengungkapkan
  Informasi Rahasia kepada Pihak Penerima.

Para Pihak sepakat sebagai berikut:

## Pasal 1 — Definisi
"Informasi Rahasia" berarti setiap informasi, baik lisan maupun tertulis,
yang diungkapkan oleh Pihak Pengungkap kepada Pihak Penerima sehubungan
dengan Tujuan.

## Pasal 2 — Kewajiban Kerahasiaan
Pihak Penerima wajib menjaga kerahasiaan Informasi Rahasia dan tidak
mengungkapkannya kepada pihak ketiga tanpa persetujuan tertulis dari
Pihak Pengungkap.

## Pasal 3 — Jangka Waktu
Kewajiban kerahasiaan berlaku selama {{ duration_months }} bulan sejak
tanggal Perjanjian ini.

{% for clause in include_clauses %}
{{ clause.title }}
{{ clause.text }}
{% endfor %}

## Pasal — Penutup
Demikian Perjanjian ini ditandatangani Para Pihak dalam rangkap dua,
masing-masing bermeterai cukup dan mempunyai kekuatan hukum yang sama.

**PIHAK PENGUNGKAP**                              **PIHAK PENERIMA**

[METERAI Rp10.000]                                 [METERAI Rp10.000]

________________________                          ________________________
{{ disclosing_party.wakil }}                     {{ receiving_party.wakil }}
