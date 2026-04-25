"""Add trend_signals table for regulatory trend analysis.

Revision ID: 003
Revises: 002
Create Date: 2026-04-24

NOTE: Uses IF NOT EXISTS so this is safe after init_db() already created the
table via Base.metadata.create_all.
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trend_signals (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id             UUID NOT NULL
                REFERENCES regulatory_documents(id) ON DELETE CASCADE,
            doc_type                VARCHAR(50)  NOT NULL,
            domain                  VARCHAR(100) NOT NULL,
            signal_strength         FLOAT        NOT NULL DEFAULT 0.5,
            horizon_months          INTEGER      NOT NULL DEFAULT 12,
            predicted_effective_date TIMESTAMPTZ  NULL,
            key_themes              TEXT         NOT NULL DEFAULT '[]',
            confidence_score        FLOAT        NOT NULL DEFAULT 0.5,
            extracted_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trend_signals_document_id "
        "ON trend_signals (document_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trend_signals_doc_type "
        "ON trend_signals (doc_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trend_signals_domain "
        "ON trend_signals (domain)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trend_signals_confidence "
        "ON trend_signals (confidence_score DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_trend_signals_confidence")
    op.execute("DROP INDEX IF EXISTS ix_trend_signals_domain")
    op.execute("DROP INDEX IF EXISTS ix_trend_signals_doc_type")
    op.execute("DROP INDEX IF EXISTS ix_trend_signals_document_id")
    op.execute("DROP TABLE IF EXISTS trend_signals")
