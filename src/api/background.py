"""Helpers for FastAPI BackgroundTasks that need their own DB session.

Background tasks run after the response is sent, so any exception they raise
is otherwise swallowed by Starlette with no rollback. This wrapper guarantees
commit-on-success, rollback-on-failure and a logged traceback.
"""
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def run_with_session(label: str, fn: Callable[[AsyncSession], Awaitable[Any]]) -> None:
    """Run ``fn(db)`` in a fresh session, committing on success."""
    from src.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            await fn(db)
            await db.commit()
            logger.info("Background task '%s' completed", label)
        except Exception:
            await db.rollback()
            logger.exception("Background task '%s' failed", label)
