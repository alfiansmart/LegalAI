# MEMO HUKUM

**Untuk**      : {{ untuk | default("Klien") }}
**Dari**       : {{ dari | default("LegalAI") }}
**Tanggal**    : {{ tanggal }}
**Re**         : {{ issue }}

---

## I. Isu Hukum
{{ issue }}

## II. Fakta
{{ facts }}

## III. Analisis Hukum
{{ analysis }}

## IV. Kesimpulan dan Rekomendasi
{{ conclusion }}

{% if evidence %}
## V. Dasar Hukum (Ringkas)
{% for e in evidence %}
- **{{ e.peraturan }} Pasal {{ e.pasal }}{% if e.ayat %} ayat ({{ e.ayat }}){% endif %}** — {{ e.snippet | default("") }}
{% endfor %}
{% endif %}

---
_Memo ini disusun berdasarkan informasi yang tersedia pada {{ tanggal }} dan
bukan nasihat hukum mengikat. Konsultasikan dengan advokat berlisensi untuk
kasus spesifik._
