"""Add performance indexes: B-tree on FK columns + HNSW on contract_clauses.embedding.

Revision ID: 001
Revises:
Create Date: 2026-04-23

NOTE: Uses IF NOT EXISTS throughout so this migration is safe to run both on
a fresh database (after init_db() creates the tables) and on an existing one.
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # B-tree indexes on frequently filtered foreign-key columns
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_regulatory_changes_document_id "
        "ON regulatory_changes (document_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_impact_alerts_document_id "
        "ON impact_alerts (document_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_impact_items_alert_id "
        "ON impact_items (alert_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_impact_items_change_id "
        "ON impact_items (change_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type "
        "ON audit_logs (entity_type)"
    )

    # HNSW vector index for fast ANN search on clause embeddings.
    # m=16 / ef_construction=64 are conservative defaults.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_contract_clauses_embedding_hnsw
        ON contract_clauses
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_contract_clauses_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_entity_type")
    op.execute("DROP INDEX IF EXISTS ix_impact_items_change_id")
    op.execute("DROP INDEX IF EXISTS ix_impact_items_alert_id")
    op.execute("DROP INDEX IF EXISTS ix_impact_alerts_document_id")
    op.execute("DROP INDEX IF EXISTS ix_regulatory_changes_document_id")
