"""Tests for the promulgation / status-clause parser.

These cover the closing-block forms that appear in real Indonesian
peraturan: Ditetapkan / Diundangkan dates + places, LN/TLN/BN
references, "mulai berlaku" effective-date computation, and the
dicabut / sebagaimana-telah-diubah reference extraction.
"""
from datetime import date

from backend.legal.promulgation import parse_promulgation


def test_ditetapkan_and_diundangkan_dates_and_places():
    text = """\
Ditetapkan di Jakarta
pada tanggal 25 Maret 2003
PRESIDEN REPUBLIK INDONESIA

Diundangkan di Jakarta
pada tanggal 25 Maret 2003
SEKRETARIS NEGARA REPUBLIK INDONESIA
"""
    p = parse_promulgation(text)
    assert p.ditetapkan_di == "Jakarta"
    assert p.diundangkan_di == "Jakarta"
    assert p.tanggal_ditetapkan == date(2003, 3, 25)
    assert p.tanggal_diundangkan == date(2003, 3, 25)


def test_lembaran_negara_and_tln_extracted():
    text = (
        "Diundangkan di Jakarta pada tanggal 25 Maret 2003. "
        "LEMBARAN NEGARA REPUBLIK INDONESIA TAHUN 2003 NOMOR 39. "
        "Tambahan Lembaran Negara Republik Indonesia Nomor 4279."
    )
    p = parse_promulgation(text)
    assert p.lembaran_negara == "LN 2003 No. 39"
    assert p.tambahan_lembaran_negara == "TLN No. 4279"


def test_berita_negara_for_permen():
    text = (
        "Diundangkan di Jakarta pada tanggal 1 Februari 2021. "
        "Berita Negara Republik Indonesia Tahun 2021 Nomor 1234."
    )
    p = parse_promulgation(text)
    assert p.berita_negara == "BN 2021 No. 1234"


def test_effective_on_promulgation_pins_effective_to_diundangkan():
    text = """\
Peraturan ini mulai berlaku pada tanggal diundangkan.

Ditetapkan di Jakarta
pada tanggal 25 Maret 2003

Diundangkan di Jakarta
pada tanggal 25 Maret 2003
"""
    p = parse_promulgation(text)
    assert p.effective_from == date(2003, 3, 25)


def test_effective_days_after_promulgation():
    text = """\
Peraturan ini mulai berlaku 30 (tiga puluh) hari sejak tanggal diundangkan.

Diundangkan di Jakarta
pada tanggal 1 Januari 2024
"""
    p = parse_promulgation(text)
    assert p.effective_from == date(2024, 1, 31)


def test_effective_explicit_date():
    text = "Peraturan ini mulai berlaku pada tanggal 1 Januari 2024."
    p = parse_promulgation(text)
    assert p.effective_from == date(2024, 1, 1)


def test_repealed_refs_extracted_from_closing_clause():
    text = (
        "Dengan berlakunya Undang-Undang ini, Undang-Undang Nomor 14 Tahun 1969 "
        "tentang Ketentuan-Ketentuan Pokok Mengenai Tenaga Kerja dicabut dan "
        "dinyatakan tidak berlaku."
    )
    p = parse_promulgation(text)
    assert any("UU" in r.lower() or "undang-undang" in r.lower() for r in p.repealed_refs)
    assert any("14" in r and "1969" in r for r in p.repealed_refs)


def test_amended_refs_extracted():
    text = (
        "Undang-Undang Nomor 13 Tahun 2003 tentang Ketenagakerjaan sebagaimana "
        "telah diubah dengan Undang-Undang Nomor 11 Tahun 2020 tentang Cipta Kerja."
    )
    p = parse_promulgation(text)
    assert any("11" in r and "2020" in r for r in p.amended_refs)


def test_empty_text_returns_empty_struct():
    p = parse_promulgation("")
    assert p.ditetapkan_di is None
    assert p.tanggal_diundangkan is None
    assert p.repealed_refs == []
    assert p.amended_refs == []


def test_archaic_month_spelling_pebruari():
    text = "Diundangkan di Jakarta pada tanggal 5 Pebruari 1985."
    p = parse_promulgation(text)
    assert p.tanggal_diundangkan == date(1985, 2, 5)
