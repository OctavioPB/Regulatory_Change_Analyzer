import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.impact import ApprovalStatus, ImpactAlert, ImpactItem, Severity

logger = logging.getLogger(__name__)


async def create_alert(
    db: AsyncSession,
    document_id: uuid.UUID,
    title: str,
) -> ImpactAlert:
    """Create and persist a new ImpactAlert."""
    alert = ImpactAlert(document_id=document_id, title=title)
    db.add(alert)
    await db.flush()
    logger.info("Created impact alert: %s (doc=%s)", title, document_id)
    return alert


async def create_item(
    db: AsyncSession,
    alert_id: uuid.UUID,
    change_id: uuid.UUID,
    impact_type: str,
    affected_name: str,
    severity: Severity,
    suggestion: str,
    clause_id: uuid.UUID | None = None,
    affected_ref: str | None = None,
) -> ImpactItem:
    """Create and persist a single ImpactItem."""
    item = ImpactItem(
        alert_id=alert_id,
        change_id=change_id,
        clause_id=clause_id,
        impact_type=impact_type,
        affected_name=affected_name,
        affected_ref=affected_ref,
        severity=severity,
        suggestion=suggestion,
    )
    db.add(item)
    await db.flush()
    return item


async def get_alert_by_id(
    db: AsyncSession,
    alert_id: uuid.UUID,
) -> ImpactAlert | None:
    """Fetch an alert by primary key, eager-loading its items."""
    result = await db.execute(
        select(ImpactAlert)
        .where(ImpactAlert.id == alert_id)
        .options(selectinload(ImpactAlert.items))
    )
    return result.scalar_one_or_none()


async def list_alerts(
    db: AsyncSession,
    unread_only: bool = False,
    limit: int = 50,
) -> list[ImpactAlert]:
    """Return alerts ordered by creation date (newest first)."""
    stmt = select(ImpactAlert).order_by(ImpactAlert.created_at.desc()).limit(limit)
    if unread_only:
        stmt = stmt.where(ImpactAlert.is_read.is_(False))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_read(db: AsyncSession, alert_id: uuid.UUID) -> bool:
    """Mark an alert as read. Returns True if found, False if not."""
    result = await db.execute(
        select(ImpactAlert).where(ImpactAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        return False
    alert.is_read = True
    await db.flush()
    return True


async def update_approval(
    db: AsyncSession,
    item_id: uuid.UUID,
    status: ApprovalStatus,
    reviewer_notes: str | None = None,
) -> ImpactItem | None:
    """Update approval status and notes for an ImpactItem."""
    result = await db.execute(
        select(ImpactItem).where(ImpactItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        return None
    item.approval_status = status
    item.reviewer_notes = reviewer_notes
    item.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    return item


async def count_by_document(db: AsyncSession, document_id: uuid.UUID) -> int:
    """Count total impact items across all alerts for a document."""
    from sqlalchemy import func

    result = await db.execute(
        select(func.count(ImpactItem.id))
        .join(ImpactAlert, ImpactAlert.id == ImpactItem.alert_id)
        .where(ImpactAlert.document_id == document_id)
    )
    return result.scalar_one() or 0
