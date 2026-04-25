import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class DocType(str, enum.Enum):
    proposed_rule = "proposed_rule"
    no_action_letter = "no_action_letter"
    interim_rule = "interim_rule"
    final_rule = "final_rule"
    guidance = "guidance"
    other = "other"


class TrendSignal(Base):
    """Regulatory trend signal extracted from a Proposed Rule or No-Action Letter."""

    __tablename__ = "trend_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_type: Mapped[DocType] = mapped_column(Enum(DocType), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    horizon_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    predicted_effective_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    key_themes: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON array
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["RegulatoryDocument"] = relationship(  # noqa: F821
        "RegulatoryDocument",
    )
