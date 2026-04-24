"""Add cross_jurisdiction_links table for multi-jurisdictional cross-mapping.

Revision ID: 002
Revises: 001
Create Date: 2026-04-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cross_jurisdiction_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_change_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("regulatory_changes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_change_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("regulatory_changes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_jurisdiction", sa.String(50), nullable=False),
        sa.Column("target_jurisdiction", sa.String(50), nullable=False),
        sa.Column("similarity_score", sa.Float, nullable=False),
        sa.Column("shared_rule_ids", sa.String(500), nullable=False, server_default="[]"),
        sa.Column("analysis", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("source_change_id", "target_change_id", name="uq_cross_link_pair"),
    )
    op.create_index("ix_cross_links_source_change_id", "cross_jurisdiction_links", ["source_change_id"])
    op.create_index("ix_cross_links_target_change_id", "cross_jurisdiction_links", ["target_change_id"])
    op.create_index("ix_cross_links_source_jurisdiction", "cross_jurisdiction_links", ["source_jurisdiction"])


def downgrade() -> None:
    op.drop_index("ix_cross_links_source_jurisdiction", table_name="cross_jurisdiction_links")
    op.drop_index("ix_cross_links_target_change_id", table_name="cross_jurisdiction_links")
    op.drop_index("ix_cross_links_source_change_id", table_name="cross_jurisdiction_links")
    op.drop_table("cross_jurisdiction_links")
