from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import RequireAnalyst, RequireViewer
from src.database import get_db
from src.services import ingestion_service

router = APIRouter(prefix="/ingest", tags=["ingestion"])

_SUPPORTED = ingestion_service.SUPPORTED_SOURCES


@router.get("/sources", dependencies=[RequireViewer])
async def list_sources() -> dict:
    """Return the list of supported regulatory sources."""
    return {"sources": _SUPPORTED}


@router.post("/", status_code=202, dependencies=[RequireAnalyst])
async def trigger_all_ingestion(background_tasks: BackgroundTasks) -> dict:
    """Trigger ingestion for all supported sources."""
    for source in _SUPPORTED:
        background_tasks.add_task(_run_ingest, source)
    return {"detail": "Ingestion queued for all sources", "sources": _SUPPORTED}


@router.post("/analyze", status_code=202, dependencies=[RequireAnalyst])
async def trigger_analyze_all(background_tasks: BackgroundTasks) -> dict:
    """Trigger NLP analysis for all documents pending analysis."""
    background_tasks.add_task(_run_analyze_all)
    return {"detail": "Analysis queued for all pending documents"}


@router.post("/map", status_code=202, dependencies=[RequireAnalyst])
async def trigger_map_all(background_tasks: BackgroundTasks) -> dict:
    """Trigger impact mapping for all documents with unprocessed changes."""
    background_tasks.add_task(_run_map_all)
    return {"detail": "Impact mapping queued"}


@router.post("/{source}", status_code=202, dependencies=[RequireAnalyst])
async def trigger_ingestion(
    source: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger document ingestion for a regulatory source.

    Runs asynchronously; returns immediately with 202 Accepted.
    """
    if source not in _SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Supported: {_SUPPORTED}",
        )
    background_tasks.add_task(_run_ingest, source)
    return {"detail": "Ingestion queued", "source": source}


async def _run_ingest(source: str) -> None:
    from src.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await ingestion_service.run(source, db)
        await db.commit()


async def _run_analyze_all() -> None:
    from src.database import AsyncSessionLocal
    from src.services import nlp_service
    async with AsyncSessionLocal() as db:
        await nlp_service.analyze_all_pending(db)
        await db.commit()


async def _run_map_all() -> None:
    from sqlalchemy import select, not_, exists
    from src.database import AsyncSessionLocal
    from src.models.document import RegulatoryDocument, RegulatoryChange
    from src.models.impact import ImpactAlert
    from src.services import impact_service
    async with AsyncSessionLocal() as db:
        stmt = (
            select(RegulatoryDocument.id)
            .join(RegulatoryChange, RegulatoryChange.document_id == RegulatoryDocument.id)
            .where(
                not_(exists(
                    select(ImpactAlert.id).where(
                        ImpactAlert.document_id == RegulatoryDocument.id
                    )
                ))
            )
            .distinct()
        )
        rows = await db.execute(stmt)
        doc_ids = [row[0] for row in rows.fetchall()]
        for did in doc_ids:
            await impact_service.map_document_impacts(did, db)
        await db.commit()
