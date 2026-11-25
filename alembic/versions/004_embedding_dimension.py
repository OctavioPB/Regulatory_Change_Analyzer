"""Resize the embedding columns to settings.embedding_dim (bge-m3: 1024).

Revision ID: 004
Revises: 003
Create Date: 2026-11-25

Vectors of another model cannot be compared with the new ones, so a column whose size changes is
emptied (set to NULL) — never truncated or padded. Run `python scripts/reembed.py` afterwards.
Idempotent: a column already at the configured size is left untouched.
"""

from alembic import op
from sqlalchemy import text

from src.config import settings

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

_COLUMNS = (("regulatory_changes", "embedding"), ("contract_clauses", "embedding"))


def _resize(dim: int) -> None:
    conn = op.get_bind()
    for table, column in _COLUMNS:
        current = conn.execute(text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = CAST(:t AS regclass) AND attname = :c AND NOT attisdropped"
        ), {"t": table, "c": column}).scalar()
        if current is None or current == dim:
            continue
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE vector({dim}) USING NULL")


def upgrade() -> None:
    _resize(settings.embedding_dim)


def downgrade() -> None:
    _resize(384)  # all-MiniLM-L6-v2, the previous default
