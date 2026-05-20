"""Phase 4: long-document RAG over uploaded contracts.

New tables:
  - document_outline  — structural tree of an uploaded document
  - document_chunk    — retrievable units with breadcrumb +
                        contextual_text + embedding
  - document_entity   — extracted parties / dates / money / obligations
  - document_citation — resolved references into the peraturan corpus
  - document_term     — defined terms from the Definitions section

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from backend.config import get_settings

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_EMBED_DIM = get_settings().embedding_dim


def upgrade() -> None:
    op.create_table(
        "document_outline",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("document.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "parent_id",
            sa.Integer,
            sa.ForeignKey("document_outline.id", ondelete="CASCADE"),
        ),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("span_start", sa.Integer),
        sa.Column("span_end", sa.Integer),
    )

    op.create_table(
        "document_chunk",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("document.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "matter_id",
            sa.Integer,
            sa.ForeignKey("matter.id", ondelete="SET NULL"),
            index=True,
        ),
        sa.Column(
            "outline_id",
            sa.Integer,
            sa.ForeignKey("document_outline.id", ondelete="SET NULL"),
        ),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("contextual_text", sa.Text),
        sa.Column("breadcrumb", sa.Text),
        sa.Column("parent_summary", sa.Text),
        sa.Column("token_count", sa.Integer),
        sa.Column("embedding", Vector(_EMBED_DIM)),
    )
    op.create_index(
        "ix_document_chunk_document",
        "document_chunk",
        ["document_id", "ordinal"],
    )
    op.create_index(
        "ix_document_chunk_embedding",
        "document_chunk",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": "100"},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "document_entity",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("document.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("span_start", sa.Integer),
        sa.Column("span_end", sa.Integer),
        sa.Column("payload", sa.JSON),
    )

    op.create_table(
        "document_citation",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("document.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "pasal_id",
            sa.Integer,
            sa.ForeignKey("pasal.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "kind",
            sa.Enum(
                "refers",
                "amends",
                "repeals",
                "implements",
                "dasar_hukum",
                "turunan",
                name="citation_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text),
        sa.UniqueConstraint(
            "document_id", "pasal_id", "kind", name="uq_document_citation"
        ),
    )

    op.create_table(
        "document_term",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("document.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("term", sa.String(255), nullable=False),
        sa.Column("definition", sa.Text, nullable=False),
        sa.Column("span_start", sa.Integer),
        sa.Column("span_end", sa.Integer),
        sa.UniqueConstraint("document_id", "term", name="uq_document_term"),
    )
    op.create_index("ix_document_term_term", "document_term", ["term"])


def downgrade() -> None:
    op.drop_index("ix_document_term_term", table_name="document_term")
    op.drop_table("document_term")
    op.drop_table("document_citation")
    op.drop_table("document_entity")
    op.drop_index("ix_document_chunk_embedding", table_name="document_chunk")
    op.drop_index("ix_document_chunk_document", table_name="document_chunk")
    op.drop_table("document_chunk")
    op.drop_table("document_outline")
