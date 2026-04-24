"""Jira Cloud REST API v3 task manager integration."""
import logging

import httpx

from src.config import settings
from src.integrations.task_manager import BaseTaskManager

logger = logging.getLogger(__name__)

_PRIORITY_MAP = {"high": "High", "medium": "Medium", "low": "Low"}


class JiraTaskManager(BaseTaskManager):
    async def create_task(self, title: str, description: str, priority: str) -> str:
        payload = {
            "fields": {
                "project": {"key": settings.jira_project_key},
                "summary": title[:255],
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                },
                "issuetype": {"name": "Task"},
                "priority": {"name": _PRIORITY_MAP.get(priority, "Medium")},
            }
        }
        auth = (settings.jira_email, settings.jira_api_token)
        url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/issue"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, auth=auth)
            resp.raise_for_status()
        issue_key: str = resp.json()["key"]
        logger.info("Created Jira issue %s", issue_key)
        return issue_key

    def task_url(self, task_id: str) -> str:
        return f"{settings.jira_base_url.rstrip('/')}/browse/{task_id}"
