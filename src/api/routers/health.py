from fastapi import APIRouter

from src.api.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health_check() -> HealthOut:
    return HealthOut(status="ok")
