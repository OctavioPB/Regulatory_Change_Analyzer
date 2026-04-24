"""Abstract task manager interface and factory."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from src.config import settings

logger = logging.getLogger(__name__)


class BaseTaskManager(ABC):
    """Push compliance review tasks to an external project management tool."""

    @abstractmethod
    async def create_task(self, title: str, description: str, priority: str) -> str:
        """Create a task and return its ID or key (tool-specific string)."""

    @abstractmethod
    def task_url(self, task_id: str) -> str:
        """Return the human-readable URL for a task ID."""


def get_task_manager() -> BaseTaskManager | None:
    """Return the configured task manager, or None if task_manager == 'none'."""
    mode = settings.task_manager.lower()
    if mode == "jira":
        from src.integrations.jira import JiraTaskManager
        return JiraTaskManager()
    if mode == "asana":
        from src.integrations.asana import AsanaTaskManager
        return AsanaTaskManager()
    if mode != "none":
        logger.warning("Unknown task_manager='%s' — task push disabled", mode)
    return None
