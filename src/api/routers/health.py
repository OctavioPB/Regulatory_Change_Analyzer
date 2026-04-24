from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import HealthOut
from src.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthOut:
    """Return application health and database connectivity status."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        db=db_status,
    )
