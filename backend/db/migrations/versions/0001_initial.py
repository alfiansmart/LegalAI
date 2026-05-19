"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions are created by docker/postgres-init.sql; this migration
    # is a no-op shim — the real DDL is auto-generated from models via
    # `alembic revision --autogenerate -m "..."`. Run that after first
    # `alembic upgrade head` of this placeholder.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    pass
