import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.models.document import ChangeType
from src.models.impact import ApprovalStatus, Severity


# ── Regulatory Documents ──────────────────────────────────────────────────────

class RegulatoryDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    title: str
    url: str | None
    publication_date: datetime
    fetched_at: datetime


class RegulatoryChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    article_ref: str | None
    change_type: ChangeType
    summary: str
    old_text: str | None
    new_text: str | None
    created_at: datetime


# ── Impact Alerts ─────────────────────────────────────────────────────────────

class ImpactItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    impact_type: str
    affected_name: str
    affected_ref: str | None
    severity: Severity
    suggestion: str
    approval_status: ApprovalStatus
    reviewer_notes: str | None
    reviewed_at: datetime | None


class ImpactAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    title: str
    is_read: bool
    created_at: datetime
    items: list[ImpactItemOut] = []


# ── Contracts ─────────────────────────────────────────────────────────────────

class ContractIn(BaseModel):
    name: str
    contract_type: str
    area: str | None = None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    contract_type: str
    area: str | None
    created_at: datetime


# ── Review actions ────────────────────────────────────────────────────────────

class ReviewAction(BaseModel):
    status: ApprovalStatus
    reviewer_notes: str | None = None


# ── Generic ───────────────────────────────────────────────────────────────────

class HealthOut(BaseModel):
    status: str
    version: str = "0.1.0"
