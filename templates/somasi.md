{{ parties[0].alamat }}
{{ tanggal }}

Nomor    : {{ nomor | default("___/Som/___/____") }}
Lampiran : -
Perihal  : **SOMASI**

Kepada Yth.
{{ parties[1].nama }}
{{ parties[1].alamat }}

Dengan hormat,

Kami yang bertanda tangan di bawah ini, bertindak untuk dan atas nama
**{{ parties[0].nama }}** ("**Klien Kami**"), berdasarkan Surat Kuasa
{% if surat_kuasa_tanggal %}tertanggal {{ surat_kuasa_tanggal | id_date }}{% endif %},
dengan ini menyampaikan **Somasi** kepada Saudara berdasarkan hal-hal berikut.

## A. Fakta-Fakta
{{ fakta }}

## B. Dasar Hukum
{% if dasar_hukum %}
{% for d in dasar_hukum %}
{{ loop.index }}. {{ d }}
{% endfor %}
{% else %}
Sesuai Pasal 1238 KUHPerdata, Saudara dianggap dalam keadaan lalai apabila
tidak memenuhi prestasi setelah ditegur secara tertulis.
{% endif %}

## C. Tuntutan
Sehubungan dengan hal tersebut, kami menuntut Saudara untuk:
{{ tuntutan }}

dalam waktu {{ tenggat_hari | default("7 (tujuh)") }} hari kalender terhitung
sejak surat ini diterima.

Apabila Saudara tidak memenuhi tuntutan di atas dalam tenggat waktu yang
ditentukan, Klien Kami akan menempuh upaya hukum yang dipandang perlu,
termasuk gugatan perdata dan/atau laporan pidana, dengan segala konsekuensi
biaya yang menjadi tanggungan Saudara.

Demikian Somasi ini disampaikan untuk dilaksanakan sebagaimana mestinya.

Hormat kami,

________________________
{{ parties[0].wakil | default(parties[0].nama) }}
