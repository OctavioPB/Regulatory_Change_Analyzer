import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


class ChangeType(str, enum.Enum):
    new_requirement = "new_requirement"
    limit_modification = "limit_modification"
    repeal = "repeal"
    clarification = "clarification"
    deadline = "deadline"
    other = "other"


class RegulatoryDocument(Base):
    """Raw regulatory publication as fetched from a source."""

    __tablename__ = "regulatory_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # "CNBV" | "SEC" | …
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=True)
    publication_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    changes: Mapped[list["RegulatoryChange"]] = relationship(
        "RegulatoryChange", back_populates="document", cascade="all, delete-orphan"
    )


class RegulatoryChange(Base):
    """A discrete change extracted from a RegulatoryDocument."""

    __tablename__ = "regulatory_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id", ondelete="CASCADE"), nullable=False
    )
    article_ref: Mapped[str] = mapped_column(String(100), nullable=True)  # "Article 5, paragraph 2"
    change_type: Mapped[ChangeType] = mapped_column(Enum(ChangeType), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    old_text: Mapped[str] = mapped_column(Text, nullable=True)
    new_text: Mapped[str] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["RegulatoryDocument"] = relationship("RegulatoryDocument", back_populates="changes")
    impact_items: Mapped[list["ImpactItem"]] = relationship(  # noqa: F821
        "ImpactItem", back_populates="change", cascade="all, delete-orphan"
    )
