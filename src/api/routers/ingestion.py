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


@router.post("/", status_code=202, dependencies=[RequireAnalyst])
async def trigger_all_ingestion(background_tasks: BackgroundTasks) -> dict:
    """Trigger ingestion for all supported sources."""
    for source in _SUPPORTED:
        background_tasks.add_task(_run_ingest, source)
    return {"detail": "Ingestion queued for all sources", "sources": _SUPPORTED}


async def _run_ingest(source: str) -> None:
    from src.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await ingestion_service.run(source, db)
        await db.commit()
