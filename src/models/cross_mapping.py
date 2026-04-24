import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CrossJurisdictionLink(Base):
    """A detected cross-jurisdictional regulatory overlap between two changes.

    Represents the finding that a change in jurisdiction A (e.g. SEC) has
    semantic and domain overlap with a change in jurisdiction B (e.g. CNBV),
    indicating potential secondary compliance implications.
    """

    __tablename__ = "cross_jurisdiction_links"
    __table_args__ = (
        UniqueConstraint("source_change_id", "target_change_id", name="uq_cross_link_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    source_change_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_change_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Denormalised for fast filtering without joins
    source_jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False)
    target_jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False)

    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    shared_rule_ids: Mapped[str] = mapped_column(
        String(500), nullable=False, default="[]"
    )  # JSON array stored as text, e.g. '["R001","R007"]'

    analysis: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source_change: Mapped["RegulatoryChange"] = relationship(  # noqa: F821
        "RegulatoryChange", foreign_keys=[source_change_id]
    )
    target_change: Mapped["RegulatoryChange"] = relationship(  # noqa: F821
        "RegulatoryChange", foreign_keys=[target_change_id]
    )
