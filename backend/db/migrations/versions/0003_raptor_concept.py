"""Phase 5: RAPTOR summary tree + concept graph tables.

These models were declared in `backend.db.models` from the start but
weren't part of the initial migration. With Phase 5 actively writing
into them, give them a proper migration.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from backend.config import get_settings

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_EMBED_DIM = get_settings().embedding_dim


def upgrade() -> None:
    op.create_table(
        "raptor_node",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column(
            "parent_id",
            sa.Integer,
            sa.ForeignKey("raptor_node.id", ondelete="CASCADE"),
        ),
        sa.Column("title", sa.Text),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("embedding", Vector(_EMBED_DIM)),
        sa.Column("payload", sa.JSON),
    )
    op.create_index(
        "ix_raptor_node_embedding",
        "raptor_node",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": "100"},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_raptor_node_parent", "raptor_node", ["parent_id"])
    op.create_index("ix_raptor_node_level", "raptor_node", ["level"])

    op.create_table(
        "concept_node",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("label", sa.String(255), nullable=False, unique=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("embedding", Vector(_EMBED_DIM)),
    )
    op.create_index(
        "ix_concept_node_embedding",
        "concept_node",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": "100"},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "concept_edge",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "src_id",
            sa.Integer,
            sa.ForeignKey("concept_node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dst_id",
            sa.Integer,
            sa.ForeignKey("concept_node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(64), nullable=False),
        sa.Column(
            "evidence_pasal_id",
            sa.Integer,
            sa.ForeignKey("pasal.id", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_concept_edge_src", "concept_edge", ["src_id"])
    op.create_index("ix_concept_edge_dst", "concept_edge", ["dst_id"])


def downgrade() -> None:
    op.drop_index("ix_concept_edge_dst", table_name="concept_edge")
    op.drop_index("ix_concept_edge_src", table_name="concept_edge")
    op.drop_table("concept_edge")
    op.drop_index("ix_concept_node_embedding", table_name="concept_node")
    op.drop_table("concept_node")
    op.drop_index("ix_raptor_node_level", table_name="raptor_node")
    op.drop_index("ix_raptor_node_parent", table_name="raptor_node")
    op.drop_index("ix_raptor_node_embedding", table_name="raptor_node")
    op.drop_table("raptor_node")
