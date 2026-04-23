import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Severity(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    modified = "modified"
    rejected = "rejected"


class ImpactAlert(Base):
    """Top-level alert grouping all impacts for one RegulatoryDocument."""

    __tablename__ = "impact_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list["ImpactItem"]] = relationship(
        "ImpactItem", back_populates="alert", cascade="all, delete-orphan"
    )


class ImpactItem(Base):
    """A single clause/process affected by a specific RegulatoryChange."""

    __tablename__ = "impact_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("impact_alerts.id", ondelete="CASCADE"), nullable=False
    )
    change_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_changes.id", ondelete="CASCADE"),
        nullable=False,
    )
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_clauses.id", ondelete="SET NULL"), nullable=True
    )
    impact_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "contract" | "process"
    affected_name: Mapped[str] = mapped_column(String(500), nullable=False)
    affected_ref: Mapped[str] = mapped_column(String(200), nullable=True)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.pending, nullable=False
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    alert: Mapped["ImpactAlert"] = relationship("ImpactAlert", back_populates="items")
    change: Mapped["RegulatoryChange"] = relationship(  # noqa: F821
        "RegulatoryChange", back_populates="impact_items"
    )
    clause: Mapped["ContractClause"] = relationship(  # noqa: F821
        "ContractClause", back_populates="impact_items"
    )
