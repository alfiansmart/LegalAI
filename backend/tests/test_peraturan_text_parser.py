"""Tests for the cleartext → ParsedPeraturan parser.

The parser is the heart of every scraper (BPK, JDIHN, future PDF
extracts), so the regex layer needs to handle the real shapes
Indonesian peraturan come in: pasal with no ayat, pasal with ayat +
huruf, mixed BAB/Bagian/Pasal text.
"""
from backend.ingest.parsers.peraturan_text import (
    _split_ayat_body,
    parse_pasal_bodies,
    parse_peraturan_text,
)


def test_pasal_without_ayat_keeps_full_body_as_teks():
    text = """\
Pasal 1
Dalam Undang-Undang ini yang dimaksud dengan Tenaga Kerja adalah setiap orang yang mampu melakukan pekerjaan.
"""
    pasals = parse_pasal_bodies(text)
    assert len(pasals) == 1
    assert pasals[0].nomor == "1"
    assert "Tenaga Kerja" in pasals[0].teks
    assert pasals[0].ayat == []


def test_pasal_with_numbered_ayat():
    text = """\
Pasal 5
(1) Setiap tenaga kerja memiliki kesempatan yang sama tanpa diskriminasi.
(2) Setiap tenaga kerja berhak memperoleh perlakuan yang sama dari pengusaha.
"""
    pasals = parse_pasal_bodies(text)
    assert len(pasals) == 1
    assert len(pasals[0].ayat) == 2
    assert pasals[0].ayat[0]["nomor"] == "1"
    assert "kesempatan yang sama" in pasals[0].ayat[0]["teks"]
    assert pasals[0].ayat[1]["nomor"] == "2"


def test_pasal_with_ayat_and_huruf():
    text = """\
Pasal 7
(1) Perjanjian kerja dibuat secara tertulis dan memuat:
a. nama, alamat perusahaan, dan jenis usaha;
b. nama, jenis kelamin, umur, dan alamat pekerja;
c. jabatan atau jenis pekerjaan.
"""
    pasals = parse_pasal_bodies(text)
    assert len(pasals) == 1
    ayat = pasals[0].ayat[0]
    assert ayat["nomor"] == "1"
    assert "huruf" in ayat
    letters = [h["huruf"] for h in ayat["huruf"]]
    assert letters == ["a", "b", "c"]
    assert "nama, alamat perusahaan" in ayat["huruf"][0]["teks"]


def test_multiple_pasal_attribute_body_correctly():
    text = """\
Pasal 1
Dalam undang-undang ini yang dimaksud dengan: Pekerja adalah setiap orang.

Pasal 2
Pelaksanaan dilakukan sesuai ketentuan yang berlaku.

Pasal 3
(1) Setiap perjanjian wajib dibuat tertulis.
(2) Perjanjian lisan tidak diakui.
"""
    pasals = parse_pasal_bodies(text)
    assert [p.nomor for p in pasals] == ["1", "2", "3"]
    assert "Pekerja" in pasals[0].teks
    assert "Pelaksanaan" in pasals[1].teks
    assert pasals[1].ayat == []
    assert len(pasals[2].ayat) == 2


def test_parse_peraturan_text_returns_seedable_dict():
    text = """\
Pasal 1
Definisi.

Pasal 2
(1) Aturan pertama.
"""
    parsed = parse_peraturan_text(
        text,
        jenis="UU",
        nomor="13",
        tahun=2003,
        judul="UU Ketenagakerjaan",
    )
    seed = parsed.to_seed_dict()
    assert seed["jenis"] == "UU"
    assert seed["nomor"] == "13"
    assert seed["tahun"] == 2003
    assert len(seed["pasal"]) == 2
    assert seed["pasal"][1]["ayat"][0]["nomor"] == "1"


def test_split_ayat_body_handles_huruf_only_clauses():
    first_line = "Yang termasuk pelanggaran adalah:"
    body = """\
a. tidak hadir tanpa keterangan;
b. menolak perintah yang sah.
"""
    teks, hurufs = _split_ayat_body(first_line, body)
    assert "Yang termasuk pelanggaran" in teks
    assert len(hurufs) == 2
    assert hurufs[0]["huruf"] == "a"
    assert "tidak hadir" in hurufs[0]["teks"]


def test_pasal_with_letter_suffix_in_nomor():
    text = """\
Pasal 5A
Pasal sisipan hasil amandemen.

Pasal 5B
Pasal sisipan kedua.
"""
    pasals = parse_pasal_bodies(text)
    assert [p.nomor for p in pasals] == ["5A", "5B"]
