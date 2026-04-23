import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.document import EMBEDDING_DIM


class Contract(Base):
    """An internal contract or policy document."""

    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(100), nullable=False)  # "loan", "derivative", …
    area: Mapped[str] = mapped_column(String(100), nullable=True)  # "AML", "Risk", …
    file_path: Mapped[str] = mapped_column(String(1000), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    clauses: Mapped[list["ContractClause"]] = relationship(
        "ContractClause", back_populates="contract", cascade="all, delete-orphan"
    )


class ContractClause(Base):
    """A single clause extracted from a Contract."""

    __tablename__ = "contract_clauses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    clause_ref: Mapped[str] = mapped_column(String(100), nullable=True)  # "Clause 4.2"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="clauses")
    impact_items: Mapped[list["ImpactItem"]] = relationship(  # noqa: F821
        "ImpactItem", back_populates="clause"
    )
