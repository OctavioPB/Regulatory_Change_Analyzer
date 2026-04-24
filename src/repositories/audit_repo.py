import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def log(
    db: AsyncSession,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: str | None = None,
    actor: str = "system",
) -> None:
    """Append an immutable audit entry.  Flush but do not commit — caller controls the tx."""
    entry = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
    )
    db.add(entry)
    await db.flush()
    logger.debug("Audit: actor=%s action=%s entity=%s/%s", actor, action, entity_type, entity_id)


async def list_recent(
    db: AsyncSession,
    entity_type: str | None = None,
    limit: int = 100,
) -> list[AuditLog]:
    """Return audit entries, newest first, optionally filtered by entity_type."""
    stmt = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    result = await db.execute(stmt)
    return list(result.scalars().all())
