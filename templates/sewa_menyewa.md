# PERJANJIAN SEWA-MENYEWA

Perjanjian Sewa-Menyewa ini dibuat pada {{ tanggal }} oleh dan antara:

1. **{{ parties[0].nama }}**, beralamat di {{ parties[0].alamat }}
   (selanjutnya disebut "**Pihak Pertama / Yang Menyewakan**");

2. **{{ parties[1].nama }}**, beralamat di {{ parties[1].alamat }}
   (selanjutnya disebut "**Pihak Kedua / Penyewa**").

Para Pihak sepakat membuat Perjanjian dengan ketentuan sebagai berikut.

## Pasal 1 — Obyek Sewa
Pihak Pertama menyewakan kepada Pihak Kedua, dan Pihak Kedua menyewa dari
Pihak Pertama, obyek sewa berupa **{{ obyek_sewa }}** yang terletak di
{{ alamat_obyek }} (selanjutnya disebut "**Obyek Sewa**").

## Pasal 2 — Jangka Waktu Sewa
Sewa berlangsung selama {{ durasi_bulan }} bulan, terhitung sejak
{{ tanggal_mulai | id_date }} sampai dengan {{ tanggal_berakhir | id_date }}.

## Pasal 3 — Harga dan Cara Pembayaran
Harga sewa adalah Rp{{ harga_sewa }} ({{ harga_sewa_terbilang }}) untuk
seluruh jangka waktu sewa. Pembayaran dilakukan dengan cara
{{ cara_pembayaran | default("transfer ke rekening Pihak Pertama") }}.

## Pasal 4 — Hak dan Kewajiban
Pihak Kedua wajib menggunakan Obyek Sewa sesuai peruntukannya, memelihara
dengan baik, dan mengembalikan dalam keadaan sebagaimana saat diterima
(Pasal 1560 KUHPerdata). Pihak Pertama menjamin Pihak Kedua menikmati Obyek
Sewa secara aman (Pasal 1551 KUHPerdata).

## Pasal 5 — Larangan
Pihak Kedua dilarang mengalihkan Obyek Sewa kepada pihak ketiga tanpa
persetujuan tertulis dari Pihak Pertama.

{% if include_clauses %}
{% for clause in include_clauses %}
## Pasal — {{ clause.title }}
{{ clause.text }}
{% endfor %}
{% endif %}

## Pasal — Penyelesaian Sengketa
Para Pihak akan menyelesaikan setiap sengketa secara musyawarah; bila tidak
tercapai, melalui {{ forum_sengketa | default("Pengadilan Negeri setempat") }}.

## Pasal — Penutup
Demikian Perjanjian ini ditandatangani Para Pihak dalam rangkap dua,
bermeterai cukup, mempunyai kekuatan hukum yang sama.

**YANG MENYEWAKAN**                                **PENYEWA**

[METERAI Rp10.000]                                 [METERAI Rp10.000]

________________________                           ________________________
{{ parties[0].nama }}                              {{ parties[1].nama }}
