import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.impact import ImpactAlert
from src.services import export_service

router = APIRouter(prefix="/export", tags=["export"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_alert(alert_id: uuid.UUID, db: AsyncSession) -> ImpactAlert:
    result = await db.execute(
        select(ImpactAlert)
        .where(ImpactAlert.id == alert_id)
        .options(selectinload(ImpactAlert.items))
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


async def _load_all_alerts(db: AsyncSession) -> list[ImpactAlert]:
    result = await db.execute(
        select(ImpactAlert)
        .options(selectinload(ImpactAlert.items))
        .order_by(ImpactAlert.created_at.desc())
    )
    return list(result.scalars().all())


# ── Per-alert endpoints ────────────────────────────────────────────────────────

@router.get("/alerts/{alert_id}.xlsx")
async def export_alert_excel(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download a single alert as an Excel (.xlsx) file."""
    alert = await _load_alert(alert_id, db)
    data = export_service.export_alert_xlsx(alert)
    filename = f"alert_{str(alert_id)[:8]}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/alerts/{alert_id}.pdf")
async def export_alert_pdf(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download a single alert as a PDF file."""
    alert = await _load_alert(alert_id, db)
    data = export_service.export_alert_pdf(alert)
    filename = f"alert_{str(alert_id)[:8]}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Bulk export endpoints ─────────────────────────────────────────────────────

@router.get("/alerts.xlsx")
async def export_all_alerts_excel(
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download all alerts as a multi-sheet Excel workbook."""
    alerts = await _load_all_alerts(db)
    if not alerts:
        raise HTTPException(status_code=404, detail="No alerts found")
    data = export_service.export_alerts_xlsx(alerts)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="regulatory_impact_report.xlsx"'},
    )
