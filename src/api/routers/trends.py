"""Trend Analysis API — Proposed Rules & No-Action Letter signal forecasting."""
import json
import math
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import Page
from src.auth.dependencies import RequireAnalyst, RequireViewer
from src.database import get_db
from src.models.trend import DocType
from src.repositories import trend_repo
from src.services import trend_service

router = APIRouter(prefix="/trends", tags=["trends"])


# ── Response schemas ──────────────────────────────────────────────────────────

class TrendSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    doc_type: DocType
    domain: str
    signal_strength: float
    horizon_months: int
    predicted_effective_date: datetime | None
    key_themes: list[str]
    confidence_score: float
    extracted_at: datetime

    @classmethod
    def from_orm(cls, obj: object) -> "TrendSignalOut":
        themes_raw = getattr(obj, "key_themes", "[]") or "[]"
        themes: list[str] = json.loads(themes_raw)
        return cls(
            id=getattr(obj, "id"),
            document_id=getattr(obj, "document_id"),
            doc_type=getattr(obj, "doc_type"),
            domain=getattr(obj, "domain"),
            signal_strength=getattr(obj, "signal_strength"),
            horizon_months=getattr(obj, "horizon_months"),
            predicted_effective_date=getattr(obj, "predicted_effective_date"),
            key_themes=themes,
            confidence_score=getattr(obj, "confidence_score"),
            extracted_at=getattr(obj, "extracted_at"),
        )


class DomainForecastOut(BaseModel):
    domain: str
    signal_count: int
    avg_strength: float
    avg_confidence: float
    avg_horizon_months: int


class TrendStatsOut(BaseModel):
    total_signals: int
    by_doc_type: dict[str, int]
    top_domain: str | None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=Page[TrendSignalOut], dependencies=[RequireViewer])
async def list_trends(
    doc_type: str | None = None,
    domain: str | None = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Page[TrendSignalOut]:
    """Return paginated trend signals, optionally filtered."""
    items, total = await trend_repo.list_signals(
        db,
        doc_type=doc_type,
        domain=domain,
        min_confidence=min_confidence,
        page=page,
        page_size=page_size,
    )
    out = [TrendSignalOut.from_orm(s) for s in items]
    return Page(
        items=out,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/forecast", response_model=list[DomainForecastOut], dependencies=[RequireViewer])
async def get_forecast(db: AsyncSession = Depends(get_db)) -> list[DomainForecastOut]:
    """Return aggregated domain-level signal forecast."""
    rows = await trend_repo.get_domain_forecast(db)
    return [DomainForecastOut(**r) for r in rows]


@router.get("/stats", response_model=TrendStatsOut, dependencies=[RequireViewer])
async def get_stats(db: AsyncSession = Depends(get_db)) -> TrendStatsOut:
    """Return summary statistics for the trend signal corpus."""
    by_type = await trend_repo.count_by_doc_type(db)
    total = sum(by_type.values())
    forecast = await trend_repo.get_domain_forecast(db)
    top_domain = forecast[0]["domain"] if forecast else None
    return TrendStatsOut(total_signals=total, by_doc_type=by_type, top_domain=top_domain)


@router.post("/extract/{document_id}", status_code=202, dependencies=[RequireAnalyst])
async def extract_signal(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
) -> dict:
    """Extract a trend signal from a specific document (async)."""
    background_tasks.add_task(_run_extract_single, document_id)
    return {"detail": "Trend extraction queued", "document_id": str(document_id)}


@router.post("/extract-all", status_code=202, dependencies=[RequireAnalyst])
async def extract_all(background_tasks: BackgroundTasks) -> dict:
    """Extract trend signals from all unprocessed documents (async)."""
    background_tasks.add_task(_run_extract_all)
    return {"detail": "Full trend extraction queued"}


# ── Background runners ────────────────────────────────────────────────────────

async def _run_extract_single(document_id: uuid.UUID) -> None:
    from src.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await trend_service.extract_signals_from_document(document_id, db)
        await db.commit()


async def _run_extract_all() -> None:
    from src.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await trend_service.extract_all_signals(db)
        await db.commit()
