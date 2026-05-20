"""Phase 7: users + matter membership + comments + suggestions + audit log.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "lawyer", "paralegal", "client", name="user_role"),
            nullable=False,
            server_default="lawyer",
        ),
        sa.Column("api_token_hash", sa.String(128)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.DateTime),
    )

    op.create_table(
        "matter_member",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "matter_id",
            sa.Integer,
            sa.ForeignKey("matter.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "role",
            sa.Enum(
                "owner", "editor", "reviewer", "viewer", name="matter_member_role"
            ),
            nullable=False,
            server_default="editor",
        ),
        sa.Column(
            "added_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("matter_id", "user_id", name="uq_matter_member"),
    )

    op.create_table(
        "comment",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("document.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("user_account.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "parent_id",
            sa.Integer,
            sa.ForeignKey("comment.id", ondelete="CASCADE"),
        ),
        sa.Column("range_start", sa.Integer),
        sa.Column("range_end", sa.Integer),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "suggestion",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("document.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("user_account.id", ondelete="SET NULL"),
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("range_start", sa.Integer, nullable=False),
        sa.Column("range_end", sa.Integer, nullable=False),
        sa.Column("base_text", sa.Text, nullable=False),
        sa.Column("proposed_text", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text),
        sa.Column(
            "status",
            sa.Enum("pending", "accepted", "rejected", name="suggestion_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("resolved_by", sa.String(64)),
        sa.Column("resolved_at", sa.DateTime),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(64)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("object_kind", sa.String(32)),
        sa.Column("object_id", sa.String(64)),
        sa.Column("payload", sa.JSON),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_log_created", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_object", "audit_log", ["object_kind", "object_id"])
    op.create_index("ix_audit_log_user", "audit_log", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_user", table_name="audit_log")
    op.drop_index("ix_audit_log_object", table_name="audit_log")
    op.drop_index("ix_audit_log_created", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("suggestion")
    op.execute("DROP TYPE IF EXISTS suggestion_status")
    op.drop_table("comment")
    op.drop_table("matter_member")
    op.execute("DROP TYPE IF EXISTS matter_member_role")
    op.drop_table("user_account")
    op.execute("DROP TYPE IF EXISTS user_role")
