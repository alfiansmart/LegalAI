# PERJANJIAN KERJA WAKTU TERTENTU (PKWT)

Nomor: {{ nomor | default("___/____/____") }}

Perjanjian Kerja Waktu Tertentu ini ("**Perjanjian**") dibuat dan ditandatangani
pada hari {{ tanggal }} oleh dan antara:

1. **{{ parties[0].nama }}**, berkedudukan di {{ parties[0].alamat }},
   dalam hal ini diwakili oleh {{ parties[0].wakil }} selaku
   {{ parties[0].jabatan }} (selanjutnya disebut "**Pemberi Kerja**");

2. **{{ parties[1].nama }}**, beralamat di {{ parties[1].alamat }},
   {% if parties[1].nik %}NIK: {{ parties[1].nik }},{% endif %}
   (selanjutnya disebut "**Pekerja**").

Para Pihak sepakat sebagai berikut:

## Pasal 1 — Jabatan dan Lingkup Kerja
Pekerja diterima bekerja pada Pemberi Kerja sebagai **{{ jabatan }}** dengan
lingkup kerja {{ lingkup_kerja | default("sebagaimana diuraikan dalam Lampiran I.") }}

## Pasal 2 — Jangka Waktu
Perjanjian ini berlaku selama {{ durasi_bulan }} bulan, terhitung sejak
{{ tanggal_mulai | id_date }} sampai dengan {{ tanggal_berakhir | id_date }}.
Perjanjian ini sesuai dengan ketentuan PKWT dalam Pasal 56-59 UU 13/2003
sebagaimana diubah dengan UU 6/2023 (Cipta Kerja).

## Pasal 3 — Upah dan Hak-Hak Pekerja
Pekerja berhak atas upah sebesar Rp{{ upah_bulanan }} per bulan, dibayarkan
setiap tanggal {{ tanggal_gaji | default("25") }}, ditambah hak-hak normatif
sesuai peraturan perundang-undangan ketenagakerjaan.

## Pasal 4 — Waktu Kerja
Waktu kerja: {{ waktu_kerja | default("Senin–Jumat, 08.00–17.00 WIB, dengan istirahat 1 (satu) jam") }}.

## Pasal 5 — Kewajiban Pekerja
Pekerja wajib:
a. melaksanakan tugas dengan itikad baik dan bertanggung jawab;
b. menjaga kerahasiaan informasi Pemberi Kerja;
c. mematuhi tata tertib perusahaan.

## Pasal 6 — Berakhirnya Perjanjian
Perjanjian berakhir karena (a) berakhirnya jangka waktu; (b) Pekerja meninggal
dunia; (c) putusan PHI; atau (d) keadaan sebagaimana diatur dalam UU Ketenagakerjaan.
Apabila Perjanjian diakhiri sebelum jangka waktu berakhir tanpa alasan yang
dibenarkan undang-undang, pihak yang mengakhiri wajib membayar ganti rugi
sebesar upah Pekerja sampai berakhirnya jangka waktu Perjanjian
(Pasal 62 UU 13/2003).

{% if include_clauses %}
{% for clause in include_clauses %}
## Pasal — {{ clause.title }}
{{ clause.text }}
{% endfor %}
{% endif %}

## Pasal — Penyelesaian Perselisihan
Setiap perselisihan diselesaikan secara musyawarah; bila tidak tercapai,
melalui bipartit, mediasi, dan/atau Pengadilan Hubungan Industrial.

## Pasal — Penutup
Demikian Perjanjian ini ditandatangani Para Pihak dalam rangkap dua,
masing-masing bermeterai cukup dan mempunyai kekuatan hukum yang sama.

**PEMBERI KERJA**                                  **PEKERJA**

[METERAI Rp10.000]                                 [METERAI Rp10.000]

________________________                           ________________________
{{ parties[0].wakil }}                             {{ parties[1].nama }}
