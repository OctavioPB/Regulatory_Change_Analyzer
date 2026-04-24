import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.repositories import audit_repo

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor: str
    action: str
    entity_type: str | None
    entity_id: str | None
    detail: str | None
    created_at: datetime


@router.get("/", response_model=list[AuditLogOut])
async def list_audit_logs(
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
) -> list:
    """Return recent audit log entries, newest first."""
    return await audit_repo.list_recent(db, entity_type=entity_type, limit=limit)
