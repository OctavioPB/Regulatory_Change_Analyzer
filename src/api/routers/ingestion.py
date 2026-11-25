from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import exists, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.background import run_with_session
from src.auth.dependencies import RequireAnalyst, RequireViewer
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
async def trigger_ingestion(source: str, background_tasks: BackgroundTasks) -> dict:
    """Trigger document ingestion for a regulatory source.

    Runs asynchronously; returns immediately with 202 Accepted.
    """
    if source.lower() not in _SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Supported: {_SUPPORTED}",
        )
    background_tasks.add_task(_run_ingest, source.lower())
    return {"detail": "Ingestion queued", "source": source.lower()}


async def _run_ingest(source: str) -> None:
    await run_with_session(f"ingest:{source}", lambda db: ingestion_service.run(source, db))


async def _run_analyze_all() -> None:
    from src.services import nlp_service

    await run_with_session("analyze-all", nlp_service.analyze_all_pending)


async def _run_map_all() -> None:
    from src.models.document import RegulatoryChange, RegulatoryDocument
    from src.models.impact import ImpactAlert
    from src.services import impact_service

    async def _map(db: AsyncSession) -> None:
        stmt = (
            select(RegulatoryDocument.id)
            .where(exists().where(RegulatoryChange.document_id == RegulatoryDocument.id))
            .where(not_(exists().where(ImpactAlert.document_id == RegulatoryDocument.id)))
        )
        doc_ids = (await db.execute(stmt)).scalars().all()
        for did in doc_ids:
            await impact_service.map_document_impacts(did, db)

    await run_with_session("map-all", _map)
