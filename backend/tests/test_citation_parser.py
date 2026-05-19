from backend.rag.citation import format_citation, parse_citations


def test_parse_kuhperdata_with_ayat_huruf():
    refs = parse_citations("Lihat Pasal 1320 ayat (1) huruf a KUHPerdata.")
    assert len(refs) == 1
    r = refs[0]
    assert r.pasal == "1320"
    assert r.ayat == "1"
    assert r.huruf == "a"
    assert r.jenis == "KUHPerdata"


def test_parse_uu_with_nomor_tahun():
    refs = parse_citations("Sesuai Pasal 5 ayat (1) UU No. 13 Tahun 2003 tentang Ketenagakerjaan.")
    assert len(refs) == 1
    r = refs[0]
    assert r.pasal == "5"
    assert r.ayat == "1"
    assert r.jenis == "UU"
    assert r.nomor == "13"
    assert r.tahun == 2003


def test_format_roundtrip():
    refs = parse_citations("Pasal 1320 ayat (1) huruf a KUHPerdata")
    assert format_citation(refs[0]) == "Pasal 1320 ayat (1) huruf a KUHPerdata"


def test_multiple_citations():
    text = "Lihat Pasal 1234 KUHPerdata dan Pasal 27 ayat (3) UUD."
    refs = parse_citations(text)
    assert len(refs) == 2


def test_no_match_returns_empty():
    assert parse_citations("Tidak ada kutipan di sini.") == []
