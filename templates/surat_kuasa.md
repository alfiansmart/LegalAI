# SURAT KUASA KHUSUS

Yang bertanda tangan di bawah ini:

Nama          : {{ parties[0].nama }}
{% if parties[0].nik %}NIK           : {{ parties[0].nik }}{% endif %}
Pekerjaan     : {{ parties[0].pekerjaan | default("-") }}
Alamat        : {{ parties[0].alamat }}

selanjutnya disebut **PEMBERI KUASA**;

dengan ini memberi kuasa khusus kepada:

Nama          : {{ parties[1].nama }}
Profesi       : {{ parties[1].profesi | default("Advokat") }}
Kantor        : {{ parties[1].alamat }}

selanjutnya disebut **PENERIMA KUASA**.

----------------------- **KHUSUS** -----------------------

Untuk dan atas nama Pemberi Kuasa, {{ keperluan }}.

Untuk maksud tersebut, Penerima Kuasa diberi wewenang untuk:
{% for w in wewenang | default([
  "mewakili Pemberi Kuasa di muka maupun di luar pengadilan",
  "menghadap dan berbicara dengan instansi pemerintah, kepolisian, kejaksaan, dan pihak ketiga lainnya",
  "menerima dan mengirimkan surat",
  "menandatangani dokumen yang diperlukan",
  "melakukan upaya hukum lainnya yang dipandang perlu"
]) %}
{{ loop.index }}. {{ w }};
{% endfor %}

Surat Kuasa ini diberikan dengan **hak substitusi** {% if hak_retensi %}**dan hak retensi**{% endif %}.

{{ kota | default("Jakarta") }}, {{ tanggal }}

**PENERIMA KUASA**                                 **PEMBERI KUASA**

[METERAI Rp10.000]                                 [METERAI Rp10.000]

________________________                           ________________________
{{ parties[1].nama }}                              {{ parties[0].nama }}
