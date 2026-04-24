import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import RequireComplianceOfficer
from src.config import settings
from src.database import get_db
from src.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/push/{alert_id}", dependencies=[RequireComplianceOfficer])
async def push_tasks(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Push all impact items of an alert to the configured task manager (Jira/Asana).

    Returns 202 with a list of created task URLs.
    Returns 503 if no task manager is configured.
    """
    try:
        pushed = await task_service.push_alert_tasks(alert_id, db)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"detail": f"{len(pushed)} task(s) created", "tasks": pushed}


@router.get("/config")
async def task_config() -> dict:
    """Return the current task manager configuration (non-sensitive)."""
    return {
        "task_manager": settings.task_manager,
        "configured": settings.task_manager != "none",
        "project_key": settings.jira_project_key if settings.task_manager == "jira" else None,
    }
