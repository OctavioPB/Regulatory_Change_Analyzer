"""Add cross_jurisdiction_links table for multi-jurisdictional cross-mapping.

Revision ID: 002
Revises: 001
Create Date: 2026-04-24

NOTE: Uses IF NOT EXISTS so this is safe after init_db() already created the
table via Base.metadata.create_all.
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cross_jurisdiction_links (
            id              UUID PRIMARY KEY,
            source_change_id UUID NOT NULL
                REFERENCES regulatory_changes(id) ON DELETE CASCADE,
            target_change_id UUID NOT NULL
                REFERENCES regulatory_changes(id) ON DELETE CASCADE,
            source_jurisdiction VARCHAR(50)  NOT NULL,
            target_jurisdiction VARCHAR(50)  NOT NULL,
            similarity_score    FLOAT        NOT NULL,
            shared_rule_ids     VARCHAR(500) NOT NULL DEFAULT '[]',
            analysis            TEXT         NOT NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_cross_link_pair UNIQUE (source_change_id, target_change_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cross_links_source_change_id "
        "ON cross_jurisdiction_links (source_change_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cross_links_target_change_id "
        "ON cross_jurisdiction_links (target_change_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cross_links_source_jurisdiction "
        "ON cross_jurisdiction_links (source_jurisdiction)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cross_links_source_jurisdiction")
    op.execute("DROP INDEX IF EXISTS ix_cross_links_target_change_id")
    op.execute("DROP INDEX IF EXISTS ix_cross_links_source_change_id")
    op.execute("DROP TABLE IF EXISTS cross_jurisdiction_links")
