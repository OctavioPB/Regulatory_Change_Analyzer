"""Add performance indexes: B-tree on FK columns + HNSW on contract_clauses.embedding.

Revision ID: 001
Revises:
Create Date: 2026-04-23
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # B-tree indexes on frequently filtered foreign-key columns
    op.create_index(
        "ix_regulatory_changes_document_id",
        "regulatory_changes",
        ["document_id"],
    )
    op.create_index(
        "ix_impact_alerts_document_id",
        "impact_alerts",
        ["document_id"],
    )
    op.create_index(
        "ix_impact_items_alert_id",
        "impact_items",
        ["alert_id"],
    )
    op.create_index(
        "ix_impact_items_change_id",
        "impact_items",
        ["change_id"],
    )
    op.create_index(
        "ix_audit_logs_entity_type",
        "audit_logs",
        ["entity_type"],
    )

    # HNSW vector index for fast approximate nearest-neighbour search on clause embeddings.
    # m=16 / ef_construction=64 are conservative defaults; tune after load testing.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_contract_clauses_embedding_hnsw
        ON contract_clauses
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_contract_clauses_embedding_hnsw", table_name="contract_clauses")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_index("ix_impact_items_change_id", table_name="impact_items")
    op.drop_index("ix_impact_items_alert_id", table_name="impact_items")
    op.drop_index("ix_impact_alerts_document_id", table_name="impact_alerts")
    op.drop_index("ix_regulatory_changes_document_id", table_name="regulatory_changes")
