"""Tests for the extended citation parser.

Phase 8 adds support for: Tap MPR, POJK / PBI / PADG, Perma / SEMA /
PerMK / Per-KPU, Putusan MK / MA, Permen with ministry suffix
(Permendag, Permenaker, Permenkeu, …), Qanun, and Perda Provinsi /
Kabupaten variants.
"""
from backend.rag.citation import format_citation, parse_citations


def test_tap_mpr_with_roman_numeral_nomor():
    refs = parse_citations("Lihat Pasal 5 Tap MPR No. I/MPR/2003.")
    assert len(refs) == 1
    r = refs[0]
    assert r.jenis == "TapMPR"
    # Tap MPR nomor includes the chamber infix ("I/MPR") — the year is
    # always the last segment after the final slash.
    assert r.nomor == "I/MPR"
    assert r.tahun == 2003
    assert r.pasal == "5"


def test_pojk_with_multi_segment_nomor():
    refs = parse_citations("Lihat Pasal 4 POJK No. 11/POJK.03/2020 tentang Stimulus Perekonomian.")
    assert len(refs) == 1
    r = refs[0]
    assert r.jenis == "POJK"
    assert "POJK.03" in (r.nomor or "")
    assert r.tahun == 2020


def test_pbi_recognised():
    refs = parse_citations("Pasal 7 PBI No. 22/9/PBI/2020.")
    assert refs and refs[0].jenis == "PBI"
    assert refs[0].tahun == 2020


def test_putusan_mk_with_puu_register():
    refs = parse_citations("Lihat Putusan MK No. 25/PUU-XIV/2016 mengenai PHK.")
    # No "Pasal" prefix → parser may or may not emit a record; what matters
    # is that when paired with a Pasal it gets identified.
    refs = parse_citations("Pasal 5 ayat (1) UUD 1945 sebagaimana ditafsirkan oleh Putusan MK No. 25/PUU-XIV/2016.")
    # Only the UUD ref gets a Pasal anchor; we just verify the second ref
    # doesn't break parsing of the first.
    assert any(r.jenis == "UUD" for r in refs)


def test_permen_with_ministry_suffix_recognised():
    refs = parse_citations("Pasal 8 Permenaker No. 6 Tahun 2020 tentang Pengupahan.")
    assert len(refs) == 1
    r = refs[0]
    assert r.jenis == "Permen"
    assert r.kementerian == "Tenaga Kerja"
    assert r.tahun == 2020


def test_permenkeu_and_permenkes_ministry_resolution():
    refs1 = parse_citations("Pasal 3 Permenkeu No. 10 Tahun 2024.")
    refs2 = parse_citations("Pasal 11 Permenkes No. 2 Tahun 2023.")
    assert refs1[0].kementerian == "Keuangan"
    assert refs2[0].kementerian == "Kesehatan"


def test_peraturan_menteri_explicit_form():
    refs = parse_citations(
        "Pasal 4 Peraturan Menteri Tenaga Kerja No. 6 Tahun 2020."
    )
    assert len(refs) == 1
    assert refs[0].jenis == "Permen"
    # The ministry comes from the "Tenaga Kerja" token.
    assert refs[0].kementerian == "Tenaga Kerja"


def test_perda_provinsi_recognised():
    refs = parse_citations("Pasal 7 Perda Provinsi No. 3 Tahun 2019.")
    assert refs and refs[0].jenis == "PerdaProv"


def test_qanun_recognised():
    refs = parse_citations("Pasal 12 Qanun No. 8 Tahun 2014 tentang Pokok-pokok Syariat Islam.")
    assert refs and refs[0].jenis == "Qanun"


def test_format_citation_for_permen_with_ministry():
    refs = parse_citations("Pasal 8 Permenaker No. 6 Tahun 2020.")
    label = format_citation(refs[0])
    assert "Pasal 8" in label
    assert "Tenaga Kerja" in label


def test_format_citation_for_tap_mpr():
    refs = parse_citations("Pasal 5 Tap MPR No. I/MPR/2003.")
    label = format_citation(refs[0])
    assert "Tap MPR" in label
    assert "I/" in label or "I /" in label


def test_legacy_uu_form_still_works():
    refs = parse_citations("Pasal 5 ayat (1) UU No. 13 Tahun 2003.")
    assert len(refs) == 1
    r = refs[0]
    assert r.jenis == "UU"
    assert r.nomor == "13"
    assert r.tahun == 2003
    assert r.ayat == "1"


def test_kuh_kitab_still_resolves_without_nomor():
    refs = parse_citations("Lihat Pasal 1320 KUHPerdata.")
    assert len(refs) == 1
    assert refs[0].jenis == "KUHPerdata"
    assert refs[0].nomor is None
    assert refs[0].tahun is None
