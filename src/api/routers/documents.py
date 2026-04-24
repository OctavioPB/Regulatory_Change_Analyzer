import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas import RegulatoryChangeOut, RegulatoryDocumentOut
from src.database import get_db
from src.models.document import RegulatoryChange, RegulatoryDocument
from src.services import nlp_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[RegulatoryDocumentOut])
async def list_documents(
    source: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[RegulatoryDocument]:
    """List regulatory documents, optionally filtered by source."""
    stmt = select(RegulatoryDocument).order_by(RegulatoryDocument.publication_date.desc()).limit(limit)
    if source:
        stmt = stmt.where(RegulatoryDocument.source == source.upper())
    result = await db.execute(stmt)
    return list(result.scalars().all())


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
