"""Tests for the BPK landing-page parser (pure HTML → ParsedPeraturan).

The HTTP fetcher needs network and is exercised manually; here we feed
representative HTML fixtures and verify the metadata + body extraction.
"""
import pytest

bs4 = pytest.importorskip("bs4")  # lxml-bound; skip the whole module if missing


from backend.ingest.scrapers.bpk import _normalise_jenis, parse_landing_page  # noqa: E402


_BPK_HTML = """
<html>
  <head><title>BPK - UU 13/2003</title></head>
  <body>
    <header>navbar</header>
    <main>
      <h1>Detail Peraturan</h1>
      <div class="metadata">
        <p>Jenis / Bentuk Peraturan : UNDANG-UNDANG</p>
        <p>Nomor : 13</p>
        <p>Tahun : 2003</p>
        <p>Tentang : KETENAGAKERJAAN</p>
        <p>Penerbit : Pemerintah Pusat</p>
        <p>Status : Berlaku</p>
      </div>
      <div id="content-isi">
        <p>BAB I KETENTUAN UMUM</p>
        <p>Pasal 1</p>
        <p>Dalam Undang-Undang ini yang dimaksud dengan Tenaga Kerja adalah setiap orang.</p>
        <p>Pasal 2</p>
        <p>(1) Pembangunan ketenagakerjaan diselenggarakan berdasarkan asas keterpaduan.</p>
        <p>(2) Pembangunan ketenagakerjaan bertujuan untuk meningkatkan kualitas hidup.</p>
      </div>
      <footer>© BPK 2024</footer>
    </main>
  </body>
</html>
"""


def test_parse_landing_page_extracts_metadata():
    parsed = parse_landing_page(_BPK_HTML, url="https://peraturan.bpk.go.id/Details/123")
    assert parsed.jenis == "UU"
    assert parsed.nomor == "13"
    assert parsed.tahun == 2003
    assert "KETENAGAKERJAAN" in parsed.tentang
    assert parsed.source_url == "https://peraturan.bpk.go.id/Details/123"


def test_parse_landing_page_extracts_pasal_bodies():
    parsed = parse_landing_page(_BPK_HTML)
    assert len(parsed.pasal) >= 2
    nomors = [p.nomor for p in parsed.pasal]
    assert "1" in nomors and "2" in nomors
    pasal2 = next(p for p in parsed.pasal if p.nomor == "2")
    assert len(pasal2.ayat) == 2


def test_normalise_jenis_maps_known_strings():
    assert _normalise_jenis("UNDANG-UNDANG") == "UU"
    assert _normalise_jenis("Peraturan Pemerintah") == "PP"
    assert _normalise_jenis("Peraturan Menteri Keuangan") == "Permen"
    assert _normalise_jenis("Peraturan Daerah") == "Perda"
    assert _normalise_jenis("perpres") == "Perpres"


def test_parser_falls_back_when_id_selector_missing():
    # Same metadata, no #content-isi div — parser should still find the
    # body via the BAB/Pasal anchor.
    html = _BPK_HTML.replace('id="content-isi"', "")
    parsed = parse_landing_page(html)
    assert len(parsed.pasal) >= 2
