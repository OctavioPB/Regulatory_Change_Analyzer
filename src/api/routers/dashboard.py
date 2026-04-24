from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.document import ChangeType, RegulatoryChange, RegulatoryDocument
from src.models.impact import ImpactAlert, ImpactItem, Severity

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """Return aggregate counts for the dashboard overview cards."""

    # Document counts
    total_docs = await _scalar(db, select(func.count(RegulatoryDocument.id)))
    sources_q = await db.execute(
        select(RegulatoryDocument.source, func.count(RegulatoryDocument.id).label("n"))
        .group_by(RegulatoryDocument.source)
    )
    docs_by_source = {row.source: row.n for row in sources_q.fetchall()}

    # Change counts by type
    changes_q = await db.execute(
        select(RegulatoryChange.change_type, func.count(RegulatoryChange.id).label("n"))
        .group_by(RegulatoryChange.change_type)
    )
    changes_by_type = {row.change_type.value: row.n for row in changes_q.fetchall()}
    total_changes = sum(changes_by_type.values())

    # Alert counts
    total_alerts = await _scalar(db, select(func.count(ImpactAlert.id)))
    unread_alerts = await _scalar(
        db,
        select(func.count(ImpactAlert.id)).where(ImpactAlert.is_read.is_(False)),
    )

    # Impact items by severity
    severity_q = await db.execute(
        select(ImpactItem.severity, func.count(ImpactItem.id).label("n"))
        .group_by(ImpactItem.severity)
    )
    items_by_severity = {row.severity.value: row.n for row in severity_q.fetchall()}
    total_items = sum(items_by_severity.values())

    # Pending reviews
    from src.models.impact import ApprovalStatus
    pending_reviews = await _scalar(
        db,
        select(func.count(ImpactItem.id)).where(
            ImpactItem.approval_status == ApprovalStatus.pending
        ),
    )

    return {
        "documents": {
            "total": total_docs,
            "by_source": docs_by_source,
        },
        "changes": {
            "total": total_changes,
            "by_type": changes_by_type,
        },
        "alerts": {
            "total": total_alerts,
            "unread": unread_alerts,
        },
        "impact_items": {
            "total": total_items,
            "by_severity": items_by_severity,
            "pending_review": pending_reviews,
        },
    }


async def _scalar(db: AsyncSession, stmt) -> int:
    result = await db.execute(stmt)
    return result.scalar_one() or 0
