"""Tests for task manager integrations (Jira + Asana) using mocked HTTP."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.task_manager import get_task_manager


# ── Factory ────────────────────────────────────────────────────────────────────

def test_get_task_manager_none_returns_none():
    with patch("src.integrations.task_manager.settings") as mock_settings:
        mock_settings.task_manager = "none"
        result = get_task_manager()
    assert result is None


def test_get_task_manager_unknown_returns_none():
    with patch("src.integrations.task_manager.settings") as mock_settings:
        mock_settings.task_manager = "linear"
        result = get_task_manager()
    assert result is None


def test_get_task_manager_jira_returns_jira_instance():
    with patch("src.integrations.task_manager.settings") as mock_settings:
        mock_settings.task_manager = "jira"
        result = get_task_manager()
    from src.integrations.jira import JiraTaskManager
    assert isinstance(result, JiraTaskManager)


def test_get_task_manager_asana_returns_asana_instance():
    with patch("src.integrations.task_manager.settings") as mock_settings:
        mock_settings.task_manager = "asana"
        result = get_task_manager()
    from src.integrations.asana import AsanaTaskManager
    assert isinstance(result, AsanaTaskManager)


# ── Jira ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jira_create_task_returns_issue_key():
    from src.integrations.jira import JiraTaskManager

    mock_response = MagicMock()
    mock_response.json.return_value = {"key": "COMP-42"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with (
        patch("src.integrations.jira.settings") as mock_settings,
        patch("src.integrations.jira.httpx.AsyncClient", return_value=mock_client),
    ):
        mock_settings.jira_base_url = "https://org.atlassian.net"
        mock_settings.jira_project_key = "COMP"
        mock_settings.jira_email = "user@org.com"
        mock_settings.jira_api_token = "token123"

        manager = JiraTaskManager()
        task_id = await manager.create_task("Title", "Description", "high")

    assert task_id == "COMP-42"
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert "COMP" in str(call_kwargs)


def test_jira_task_url():
    from src.integrations.jira import JiraTaskManager

    with patch("src.integrations.jira.settings") as mock_settings:
        mock_settings.jira_base_url = "https://org.atlassian.net"
        manager = JiraTaskManager()
        url = manager.task_url("COMP-42")

    assert url == "https://org.atlassian.net/browse/COMP-42"


@pytest.mark.asyncio
async def test_jira_maps_severity_to_priority():
    from src.integrations.jira import JiraTaskManager

    mock_response = MagicMock()
    mock_response.json.return_value = {"key": "COMP-1"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with (
        patch("src.integrations.jira.settings") as mock_settings,
        patch("src.integrations.jira.httpx.AsyncClient", return_value=mock_client),
    ):
        mock_settings.jira_base_url = "https://org.atlassian.net"
        mock_settings.jira_project_key = "COMP"
        mock_settings.jira_email = "u@x.com"
        mock_settings.jira_api_token = "t"

        manager = JiraTaskManager()
        await manager.create_task("T", "D", "low")

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["fields"]["priority"]["name"] == "Low"


# ── Asana ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_asana_create_task_returns_gid():
    from src.integrations.asana import AsanaTaskManager

    mock_response = MagicMock()
    mock_response.json.return_value = {"data": {"gid": "999888777"}}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with (
        patch("src.integrations.asana.settings") as mock_settings,
        patch("src.integrations.asana.httpx.AsyncClient", return_value=mock_client),
    ):
        mock_settings.asana_access_token = "Bearer-token"
        mock_settings.asana_project_gid = "111222333"

        manager = AsanaTaskManager()
        task_id = await manager.create_task("Title", "Description", "medium")

    assert task_id == "999888777"


def test_asana_task_url():
    from src.integrations.asana import AsanaTaskManager

    with patch("src.integrations.asana.settings") as mock_settings:
        mock_settings.asana_project_gid = "111222333"
        manager = AsanaTaskManager()
        url = manager.task_url("999888777")

    assert url == "https://app.asana.com/0/111222333/999888777"


# ── task_service ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_push_alert_tasks_no_manager_raises():
    from src.services import task_service

    db = AsyncMock()
    with patch("src.services.task_service.get_task_manager", return_value=None):
        with pytest.raises(RuntimeError, match="No task manager configured"):
            await task_service.push_alert_tasks(uuid.uuid4(), db)


@pytest.mark.asyncio
async def test_push_alert_tasks_alert_not_found_raises():
    from src.services import task_service

    mock_manager = MagicMock()
    db = AsyncMock()
    # Use an explicit MagicMock so scalar_one_or_none() is synchronous (not a coroutine)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    with patch("src.services.task_service.get_task_manager", return_value=mock_manager):
        with pytest.raises(ValueError, match="not found"):
            await task_service.push_alert_tasks(uuid.uuid4(), db)


@pytest.mark.asyncio
async def test_push_alert_tasks_creates_one_task_per_item():
    from src.services import task_service
    from src.models.impact import ImpactAlert, ImpactItem, Severity

    item1 = MagicMock(spec=ImpactItem)
    item1.id = uuid.uuid4()
    item1.affected_name = "Contrato A"
    item1.affected_ref = "Clause 4.2"
    item1.severity = Severity.high
    item1.suggestion = "Update exposure limit."

    item2 = MagicMock(spec=ImpactItem)
    item2.id = uuid.uuid4()
    item2.affected_name = "Proceso B"
    item2.affected_ref = None
    item2.severity = Severity.medium
    item2.suggestion = "Revise validation step."

    alert = MagicMock(spec=ImpactAlert)
    alert.id = uuid.uuid4()
    alert.title = "Test Alert"
    alert.items = [item1, item2]

    db = AsyncMock()
    # Explicit MagicMock so scalar_one_or_none() is synchronous (not a coroutine)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = alert
    db.execute = AsyncMock(return_value=result_mock)

    mock_manager = MagicMock()
    mock_manager.create_task = AsyncMock(side_effect=["COMP-1", "COMP-2"])
    mock_manager.task_url = MagicMock(side_effect=["http://j/COMP-1", "http://j/COMP-2"])

    with (
        patch("src.services.task_service.get_task_manager", return_value=mock_manager),
        patch("src.services.task_service.audit_repo.log", new_callable=AsyncMock),
    ):
        pushed = await task_service.push_alert_tasks(alert.id, db)

    assert len(pushed) == 2
    assert pushed[0]["task_id"] == "COMP-1"
    assert pushed[1]["task_url"] == "http://j/COMP-2"
