"""Asana REST API task manager integration."""
import logging

import httpx

from src.config import settings
from src.integrations.task_manager import BaseTaskManager

logger = logging.getLogger(__name__)

_ASANA_TASKS_URL = "https://app.asana.com/api/1.0/tasks"


class AsanaTaskManager(BaseTaskManager):
    async def create_task(self, title: str, description: str, priority: str) -> str:
        payload = {
            "data": {
                "name": title[:255],
                "notes": description,
                "projects": [settings.asana_project_gid],
            }
        }
        headers = {
            "Authorization": f"Bearer {settings.asana_access_token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_ASANA_TASKS_URL, json=payload, headers=headers)
            resp.raise_for_status()
        task_gid: str = resp.json()["data"]["gid"]
        logger.info("Created Asana task %s", task_gid)
        return task_gid

    def task_url(self, task_id: str) -> str:
        return f"https://app.asana.com/0/{settings.asana_project_gid}/{task_id}"
