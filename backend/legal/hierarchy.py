"""Indonesian legal hierarchy per UU No. 12 Tahun 2011 (as amended by
UU 15/2019 and UU 13/2022).

Article 7 — fixed hierarchy:

    1. UUD 1945                  (level 1)
    2. Ketetapan MPR (Tap MPR)   (level 2)
    3. UU / Perppu               (level 3)
    4. Peraturan Pemerintah      (level 4)
    5. Peraturan Presiden        (level 5)
    6. Perda Provinsi            (level 6)
    7. Perda Kabupaten/Kota      (level 7)

Article 8 — body-issued regulations (MPR, DPR, DPD, MA, MK, BPK, KY, BI,
Menteri, lembaga, komisi). They are legally binding when ordered by a
higher law or made within the issuing body's authority, but they do not
have a fixed slot in the hierarchy. We assign them a *nominal* level
that places them just below Perpres (5) and above Perda (6) — that
matches how courts treat them in practice when a Permen conflicts with
a Perda Provinsi, the Permen typically wins on subject-matter authority.

Two helpers anchor the rest of the system:

  - `level_of(jenis)` → int             (1 = highest, larger = lower)
  - `is_higher_than(a, b)` → bool       (lex superior)
  - `hierarchy_boost(level)` → float    (additive bump for retrieval)

The boost values are conservative (0.10 at the top, 0.0 at the bottom)
so a strong textual match on a lower-level row still wins, but a tie
on two equally relevant texts goes to the higher authority.
"""
from __future__ import annotations


# Canonical level per UU 12/2011 Article 7, plus a defensible position
# for Article 8 issuers between Perpres and Perda. Lower number = higher.
_LEVEL_TABLE: dict[str, int] = {
    # Article 7
    "UUD": 1,
    "TapMPR": 2,
    "UU": 3,
    "Perppu": 3,  # equal to UU per Article 7
    "PP": 4,
    "Perpres": 5,
    # Aggregated kitab — treat as their effective tier.
    # KUHP/KUHPerdata/KUHAP were enacted as Staatsblad; today they are
    # treated as UU-level when interpreting validity.
    "KUHP": 3,
    "KUHPerdata": 3,
    "KUHAP": 3,
    # Article 8 — body-issued, slotted between Perpres and Perda.
    "Permen": 6,
    "PerKPU": 6,
    "POJK": 6,
    "PBI": 6,
    "PADG": 6,
    "Perka": 6,
    "Perma": 6,
    "SEMA": 7,  # SEMA is technically a circular letter, not a regulation
    "PerMK": 6,
    # Putusan are quasi-source via judicial review; treat as level 3 (UU)
    # for Putusan MK (binding constitutional review) and level 6 for
    # Putusan MA (treated as persuasive precedent on regulation review).
    "PutusanMK": 3,
    "PutusanMA": 6,
    # Article 7 continued
    "PerdaProv": 7,
    "PerdaKab": 8,
    "Qanun": 7,  # Aceh equivalent of Perda Provinsi
    "Perda": 7,  # backward-compat; new rows should use PerdaProv / PerdaKab
    "Lainnya": 9,
}


_BOOST_BY_LEVEL: dict[int, float] = {
    1: 0.10,  # UUD
    2: 0.08,
    3: 0.06,
    4: 0.05,
    5: 0.04,
    6: 0.02,
    7: 0.01,
    8: 0.005,
    9: 0.0,
}


def level_of(jenis: str | None) -> int:
    """Return the hierarchy level (1=highest). Unknown → bottom slot (9)."""
    if not jenis:
        return 9
    return _LEVEL_TABLE.get(jenis, 9)


def is_higher_than(a: str | None, b: str | None) -> bool:
    """True when `a` outranks `b` in the hierarchy (lex superior)."""
    return level_of(a) < level_of(b)


def hierarchy_boost(level: int | None) -> float:
    """Additive score bump for the retriever.

    A row at level 1 gets +0.10 added to its hybrid score; a row at
    level 9 gets +0.0. Values are tuned to be small enough that a
    weak match on a UU can't outrank a strong match on a Permen —
    but a *tie* on two equally relevant rows goes to the UU.
    """
    if level is None:
        return 0.0
    return _BOOST_BY_LEVEL.get(level, 0.0)


def is_article_7(jenis: str | None) -> bool:
    """True for the fixed-hierarchy types listed in Article 7."""
    return jenis in {
        "UUD",
        "TapMPR",
        "UU",
        "Perppu",
        "PP",
        "Perpres",
        "PerdaProv",
        "PerdaKab",
        "Perda",  # legacy
        "Qanun",
    }


def is_article_8(jenis: str | None) -> bool:
    """True for body-issued peraturan covered by Article 8."""
    return jenis in {
        "Permen",
        "Perma",
        "SEMA",
        "PerMK",
        "PerKPU",
        "POJK",
        "PBI",
        "PADG",
        "Perka",
    }
