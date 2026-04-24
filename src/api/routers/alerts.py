import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas import ImpactAlertOut, Page, ReviewAction
from src.auth.dependencies import RequireComplianceOfficer, RequireViewer
from src.database import get_db
from src.models.audit import AuditLog
from src.models.impact import ImpactAlert, ImpactItem

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=Page[ImpactAlertOut])
async def list_alerts(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: None = RequireViewer,
) -> Page[ImpactAlertOut]:
    """Return paginated impact alerts, optionally filtered to unread ones."""
    base_stmt = select(ImpactAlert).where(
        ImpactAlert.is_read.is_(False) if unread_only else True
    )
    total: int = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()

    stmt = (
        base_stmt.options(selectinload(ImpactAlert.items))
        .order_by(ImpactAlert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


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
    _: None = RequireComplianceOfficer,
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
