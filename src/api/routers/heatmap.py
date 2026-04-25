"""Risk Heatmap API — regulatory churn by business department."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import RequireViewer
from src.database import get_db
from src.services import heatmap_service

router = APIRouter(prefix="/heatmap", tags=["heatmap"])


# ── Response schemas ──────────────────────────────────────────────────────────

class DepartmentSummary(BaseModel):
    department: str
    total: int
    high: int
    medium: int
    low: int
    recent_30d: int
    churn_score: float


class MatrixCell(BaseModel):
    department: str
    change_type: str
    count: int
    severity_score: float


class MonthlyPoint(BaseModel):
    department: str
    month: str
    count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/departments", response_model=list[DepartmentSummary], dependencies=[RequireViewer])
async def get_departments(db: AsyncSession = Depends(get_db)) -> list[DepartmentSummary]:
    """Per-department impact counts, severity breakdown, and churn score."""
    rows = await heatmap_service.get_department_summary(db)
    return [DepartmentSummary(**r) for r in rows]


@router.get("/matrix", response_model=list[MatrixCell], dependencies=[RequireViewer])
async def get_matrix(db: AsyncSession = Depends(get_db)) -> list[MatrixCell]:
    """Department × change_type impact count matrix."""
    rows = await heatmap_service.get_matrix(db)
    return [MatrixCell(**r) for r in rows]


@router.get("/trend", response_model=list[MonthlyPoint], dependencies=[RequireViewer])
async def get_monthly_trend(
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
) -> list[MonthlyPoint]:
    """Department impact counts by month for the last N months."""
    rows = await heatmap_service.get_monthly_trend(db, months=months)
    return [MonthlyPoint(**r) for r in rows]
