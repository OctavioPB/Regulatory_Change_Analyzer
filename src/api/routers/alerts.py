import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas import ImpactAlertOut, ReviewAction
from src.database import get_db
from src.models.audit import AuditLog
from src.models.impact import ImpactAlert, ImpactItem

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=list[ImpactAlertOut])
async def list_alerts(
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[ImpactAlert]:
    """Return all impact alerts, optionally filtered to unread ones."""
    stmt = select(ImpactAlert).options(selectinload(ImpactAlert.items)).order_by(
        ImpactAlert.created_at.desc()
    )
    if unread_only:
        stmt = stmt.where(ImpactAlert.is_read.is_(False))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{alert_id}", response_model=ImpactAlertOut)
async def get_alert(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ImpactAlert:
    stmt = (
        select(ImpactAlert)
        .options(selectinload(ImpactAlert.items))
        .where(ImpactAlert.id == alert_id)
    )
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    return alert


@router.post("/{alert_id}/items/{item_id}/review", response_model=dict)
async def review_item(
    alert_id: uuid.UUID,
    item_id: uuid.UUID,
    action: ReviewAction,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit a compliance officer's review decision on an impact item."""
    result = await db.execute(select(ImpactItem).where(ImpactItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Impact item not found")

    item.approval_status = action.status
    item.reviewer_notes = action.reviewer_notes
    item.reviewed_at = datetime.now(tz=timezone.utc)

    db.add(AuditLog(
        actor="reviewer",
        action=f"item_{action.status.value}",
        entity_type="ImpactItem",
        entity_id=str(item_id),
        detail=action.reviewer_notes,
    ))

    return {"detail": "Review recorded", "status": action.status.value}
