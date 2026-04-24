"""Push ImpactAlert items to an external task management tool."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.integrations.task_manager import get_task_manager
from src.models.impact import ImpactAlert, ImpactItem
from src.repositories import audit_repo

logger = logging.getLogger(__name__)


async def push_alert_tasks(alert_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Create one external task per ImpactItem in the alert.

    Returns a list of dicts with item_id, task_id, and task_url for each item.
    Raises ValueError if the alert does not exist.
    Raises RuntimeError if no task manager is configured.
    """
    manager = get_task_manager()
    if manager is None:
        raise RuntimeError("No task manager configured (task_manager='none')")

    result = await db.execute(
        select(ImpactAlert)
        .options(selectinload(ImpactAlert.items))
        .where(ImpactAlert.id == alert_id)
    )
    alert: ImpactAlert | None = result.scalar_one_or_none()
    if alert is None:
        raise ValueError(f"Alert {alert_id} not found")

    pushed: list[dict] = []
    for item in alert.items:
        title = f"[RCA] {item.affected_name} — {alert.title[:80]}"
        description = (
            f"Severity: {item.severity.value}\n\n"
            f"Affected: {item.affected_name}"
            + (f" ({item.affected_ref})" if item.affected_ref else "")
            + f"\n\nSuggestion:\n{item.suggestion}"
        )
        task_id = await manager.create_task(title, description, item.severity.value)
        task_url = manager.task_url(task_id)

        await audit_repo.log(
            db,
            action="task_created",
            entity_type="ImpactItem",
            entity_id=str(item.id),
            detail=task_url,
        )
        pushed.append({"item_id": str(item.id), "task_id": task_id, "task_url": task_url})
        logger.info("Pushed task %s for item %s", task_id, item.id)

    return pushed
