import math
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import Page, RegulatoryChangeOut, RegulatoryDocumentOut
from src.database import get_db
from src.models.document import RegulatoryChange, RegulatoryDocument
from src.services import nlp_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=Page[RegulatoryDocumentOut])
async def list_documents(
    source: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Page[RegulatoryDocumentOut]:
    """List regulatory documents with pagination, optionally filtered by source."""
    base_stmt = select(RegulatoryDocument)
    if source:
        base_stmt = base_stmt.where(RegulatoryDocument.source == source.upper())

    total: int = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()

    stmt = (
        base_stmt.order_by(RegulatoryDocument.publication_date.desc())
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


@router.get("/{document_id}", response_model=RegulatoryDocumentOut)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RegulatoryDocument:
    result = await db.execute(
        select(RegulatoryDocument).where(RegulatoryDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/changes", response_model=list[RegulatoryChangeOut])
async def get_document_changes(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[RegulatoryChange]:
    """Return all detected changes for a regulatory document."""
    result = await db.execute(
        select(RegulatoryChange)
        .where(RegulatoryChange.document_id == document_id)
        .order_by(RegulatoryChange.created_at)
    )
    return list(result.scalars().all())


@router.post("/{document_id}/analyze", status_code=202)
async def trigger_analysis(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger NLP analysis for a document asynchronously."""
    result = await db.execute(
        select(RegulatoryDocument).where(RegulatoryDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    background_tasks.add_task(_run_analysis, document_id)
    return {"detail": "Analysis queued", "document_id": str(document_id)}


async def _run_analysis(document_id: uuid.UUID) -> None:
    from src.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await nlp_service.analyze_document(document_id, db)
        await db.commit()
