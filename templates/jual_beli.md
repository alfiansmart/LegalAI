# PERJANJIAN JUAL BELI

Perjanjian Jual Beli ini dibuat pada {{ tanggal }} oleh dan antara:

1. **{{ parties[0].nama }}**, beralamat di {{ parties[0].alamat }}
   (selanjutnya disebut "**Penjual**");

2. **{{ parties[1].nama }}**, beralamat di {{ parties[1].alamat }}
   (selanjutnya disebut "**Pembeli**").

## Pasal 1 — Obyek Jual Beli
Penjual menjual dan Pembeli membeli {{ obyek }} dengan spesifikasi:
{{ spesifikasi | default("sebagaimana diuraikan dalam Lampiran.") }}

## Pasal 2 — Harga
Harga total adalah Rp{{ harga }} ({{ harga_terbilang }}).

## Pasal 3 — Cara Pembayaran
Pembayaran dilakukan dengan cara {{ cara_pembayaran | default("transfer ke rekening Penjual") }}
paling lambat {{ jatuh_tempo | id_date }}.

## Pasal 4 — Penyerahan
Penjual wajib menyerahkan obyek kepada Pembeli paling lambat
{{ tanggal_penyerahan | id_date }} di {{ tempat_penyerahan }}.

## Pasal 5 — Jaminan Penjual
Penjual menjamin obyek bebas dari sita, gadai, dan beban apa pun, serta
bertanggung jawab atas cacat tersembunyi sesuai Pasal 1504 KUHPerdata.

{% if include_clauses %}
{% for clause in include_clauses %}
## Pasal — {{ clause.title }}
{{ clause.text }}
{% endfor %}
{% endif %}

## Pasal — Penutup
Demikian Perjanjian ini ditandatangani dalam rangkap dua, bermeterai cukup.

**PENJUAL**                                        **PEMBELI**

[METERAI Rp10.000]                                 [METERAI Rp10.000]

________________________                           ________________________
{{ parties[0].nama }}                              {{ parties[1].nama }}
