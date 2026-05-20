"""Tests for the document outline parser.

Goal: catch the obvious failure modes — wrong nesting, missed Pasal,
missed numbered clauses, missed Definitions sections.
"""
from backend.rag.doc_structure import find_definitions_node, parse_structure


def test_peraturan_style_bab_bagian_pasal_nesting():
    text = """\
BAB I
KETENTUAN UMUM

Bagian Kesatu
Definisi

Pasal 1
Dalam undang-undang ini yang dimaksud dengan:
(1) Tenaga Kerja adalah setiap orang...
(2) Pekerja/buruh adalah setiap orang...

Pasal 2
Pelaksanaan dilakukan sebagaimana ketentuan...

BAB II
HAK DAN KEWAJIBAN

Pasal 3
Setiap pekerja berhak atas...
"""
    root = parse_structure(text)
    babs = [c for c in root.children if c.kind == "bab"]
    assert len(babs) == 2, f"expected 2 BAB, got {len(babs)}"
    assert "KETENTUAN UMUM" in (babs[0].title or "")
    # Bagian should be a child of BAB I
    bagians = [c for c in babs[0].children if c.kind == "bagian"]
    assert len(bagians) == 1
    # Pasal 1 and Pasal 2 should be under Bagian Kesatu (since it comes
    # before them). Pasal 3 should be under BAB II directly.
    bag = bagians[0]
    pasals_under_bag = [c for c in bag.children if c.kind == "pasal"]
    assert len(pasals_under_bag) == 2
    assert pasals_under_bag[0].title and "Pasal 1" in pasals_under_bag[0].title
    pasals_bab2 = [c for c in babs[1].children if c.kind == "pasal"]
    assert len(pasals_bab2) == 1
    assert "Pasal 3" in (pasals_bab2[0].title or "")


def test_contract_style_numbered_clauses_nest_by_dot_depth():
    text = """\
1. Lingkup Kerjasama
Para Pihak sepakat bekerja sama dalam...

1.1 Layanan Vendor
Vendor menyediakan jasa pemeliharaan...

1.2 Layanan Klien
Klien menyediakan fasilitas...

2. Jangka Waktu
Perjanjian berlaku selama dua puluh empat bulan.
"""
    root = parse_structure(text)
    tops = [c for c in root.children if c.kind == "clause"]
    assert len(tops) == 2, f"expected two top-level clauses, got {len(tops)}: {[t.title for t in tops]}"
    assert "Lingkup" in (tops[0].title or "")
    subs = [c for c in tops[0].children if c.kind == "clause"]
    assert len(subs) == 2, "1.1 and 1.2 should nest under 1."


def test_definitions_section_detected_by_keyword():
    text = """\
PERJANJIAN LAYANAN

Definitions
"Pihak Penjual" berarti PT Alpha Mandiri.
"Pihak Pembeli" berarti PT Beta Sejahtera.

Section 1. Term
The Term of this Agreement shall be 24 months.
"""
    root = parse_structure(text)
    defs = find_definitions_node(root)
    assert defs is not None
    assert defs.kind == "definitions"


def test_definitions_section_detected_by_ketentuan_umum_in_bab_title():
    text = """\
BAB I  KETENTUAN UMUM

Pasal 1
Dalam peraturan ini yang dimaksud dengan: Pekerja adalah setiap orang...
"""
    root = parse_structure(text)
    defs = find_definitions_node(root)
    assert defs is not None
    assert defs.kind == "bab"
    assert "KETENTUAN UMUM" in (defs.title or "")


def test_empty_document_yields_root_only():
    root = parse_structure("Sekedar paragraf bebas tanpa heading.")
    assert root.kind == "root"
    assert root.children == []


def test_breadcrumb_walks_back_to_top():
    text = """\
BAB I
KETENTUAN UMUM

Bagian Kesatu

Pasal 1
Ketentuan ini...
"""
    root = parse_structure(text)
    # find the Pasal 1 node
    pasal = next(n for n in root.walk() if n.kind == "pasal")
    crumb = pasal.breadcrumb()
    assert "Pasal 1" in crumb
    assert "Bagian Kesatu" in crumb
    assert "BAB I" in crumb
