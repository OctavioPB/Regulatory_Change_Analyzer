"""Cross-jurisdictional mapping API endpoints."""
import math
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import CrossLinkOut, Page
from src.auth.dependencies import RequireAnalyst, RequireViewer
from src.database import get_db
from src.repositories import cross_mapping_repo
from src.services import cross_mapping_service

router = APIRouter(prefix="/cross-mapping", tags=["cross-mapping"])


@router.get("/", response_model=Page[CrossLinkOut], dependencies=[RequireViewer])
async def list_cross_links(
    source_jurisdiction: str | None = None,
    target_jurisdiction: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Page[CrossLinkOut]:
    """Return all detected cross-jurisdictional links, optionally filtered."""
    items, total = await cross_mapping_repo.list_all_links(
        db,
        source_jurisdiction=source_jurisdiction,
        target_jurisdiction=target_jurisdiction,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/change/{change_id}", response_model=list[CrossLinkOut], dependencies=[RequireViewer])
async def get_links_for_change(
    change_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[CrossLinkOut]:
    """Return all cross-jurisdictional links associated with a specific change."""
    return await cross_mapping_repo.list_links_for_change(db, change_id)


@router.post("/scan/{change_id}", status_code=202, dependencies=[RequireAnalyst])
async def scan_change(
    change_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a cross-jurisdictional scan for a single change (async)."""
    from sqlalchemy import select
    from src.models.document import RegulatoryChange

    result = await db.execute(
        select(RegulatoryChange.id).where(RegulatoryChange.id == change_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Change not found")

    background_tasks.add_task(_run_scan, change_id)
    return {"detail": "Cross-mapping scan queued", "change_id": str(change_id)}


@router.post("/scan-all", status_code=202, dependencies=[RequireAnalyst])
async def scan_all(background_tasks: BackgroundTasks) -> dict:
    """Trigger a full cross-jurisdictional scan for all changes (async)."""
    background_tasks.add_task(_run_scan_all)
    return {"detail": "Full cross-mapping scan queued"}


# ── Background runners ────────────────────────────────────────────────────────

async def _run_scan(change_id: uuid.UUID) -> None:
    from src.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await cross_mapping_service.scan_change(change_id, db)
        await db.commit()


async def _run_scan_all() -> None:
    from src.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await cross_mapping_service.scan_all_changes(db)
        await db.commit()
