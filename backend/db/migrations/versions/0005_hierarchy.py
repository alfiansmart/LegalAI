"""Phase 8: hierarchy + promulgation metadata + extended JenisPeraturan.

Adds to the Peraturan row:
  - hierarchy_level         — int, per UU 12/2011 Article 7/8
  - ditetapkan_di           — city where enacted
  - lembaran_negara         — LN reference ("LN 2003 No. 39")
  - tambahan_lembaran_negara — TLN reference
  - berita_negara           — BN reference (for Permen and below)
  - kementerian             — sub-type discriminator for Permen
  - daerah                  — province / city for Perda

Adds enum values to JenisPeraturan: TapMPR, PerdaProv, PerdaKab,
Perma, SEMA, PerMK, PerKPU, POJK, PBI, PADG, Perka, PutusanMK,
PutusanMA, Qanun.

Postgres enum extension is one-directional — downgrade restores the
column drops but leaves the enum values in place (cleanest path is a
full enum recreate, which is too disruptive to be worth the rollback
guarantee).

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


# Enum values added in this migration.
_NEW_JENIS_VALUES = [
    "TapMPR",
    "PerdaProv",
    "PerdaKab",
    "Perma",
    "SEMA",
    "PerMK",
    "PerKPU",
    "POJK",
    "PBI",
    "PADG",
    "Perka",
    "PutusanMK",
    "PutusanMA",
    "Qanun",
]


def upgrade() -> None:
    # ALTER TYPE … ADD VALUE has to run outside a transaction block.
    with op.get_context().autocommit_block():
        for value in _NEW_JENIS_VALUES:
            op.execute(
                f"ALTER TYPE jenis_peraturan ADD VALUE IF NOT EXISTS '{value}'"
            )

    # New columns on peraturan.
    op.add_column("peraturan", sa.Column("hierarchy_level", sa.Integer))
    op.add_column("peraturan", sa.Column("ditetapkan_di", sa.String(128)))
    op.add_column("peraturan", sa.Column("lembaran_negara", sa.String(128)))
    op.add_column(
        "peraturan", sa.Column("tambahan_lembaran_negara", sa.String(128))
    )
    op.add_column("peraturan", sa.Column("berita_negara", sa.String(128)))
    op.add_column("peraturan", sa.Column("kementerian", sa.String(255)))
    op.add_column("peraturan", sa.Column("daerah", sa.String(255)))

    op.create_index("ix_peraturan_level", "peraturan", ["hierarchy_level"])


def downgrade() -> None:
    op.drop_index("ix_peraturan_level", table_name="peraturan")
    for col in [
        "daerah",
        "kementerian",
        "berita_negara",
        "tambahan_lembaran_negara",
        "lembaran_negara",
        "ditetapkan_di",
        "hierarchy_level",
    ]:
        op.drop_column("peraturan", col)
    # Note: ALTER TYPE … DROP VALUE is not supported in Postgres. The
    # added enum labels stay; that is harmless for the columns we just
    # dropped.
