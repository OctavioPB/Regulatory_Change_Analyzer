"""Tests for paginated list endpoints and Page schema."""
import math
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.schemas import Page


# ── Page schema ───────────────────────────────────────────────────────────────

def test_page_schema_fields():
    p = Page(items=["a", "b"], total=25, page=2, page_size=10, pages=3)
    assert p.items == ["a", "b"]
    assert p.total == 25
    assert p.page == 2
    assert p.page_size == 10
    assert p.pages == 3


def test_page_schema_single_page():
    p = Page(items=[], total=0, page=1, page_size=20, pages=1)
    assert p.pages == 1


# ── Alert pagination helper ───────────────────────────────────────────────────

def _make_alert(n: int) -> list:
    """Create n simple mock alerts."""
    from src.models.impact import ImpactAlert
    alerts = []
    for _ in range(n):
        a = MagicMock(spec=ImpactAlert)
        a.id = uuid.uuid4()
        a.items = []
        alerts.append(a)
    return alerts


@pytest.mark.asyncio
async def test_list_alerts_returns_page_schema():
    from src.api.routers.alerts import list_alerts

    alerts = _make_alert(5)

    db = AsyncMock()

    # First execute call → count query
    count_result = MagicMock()
    count_result.scalar_one.return_value = 5
    # Second execute call → items query
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = alerts

    db.execute.side_effect = [count_result, items_result]

    result = await list_alerts(unread_only=False, page=1, page_size=20, db=db, _=None)

    assert isinstance(result, Page)
    assert result.total == 5
    assert result.page == 1
    assert result.page_size == 20
    assert result.pages == 1
    assert len(result.items) == 5


@pytest.mark.asyncio
async def test_list_alerts_second_page():
    from src.api.routers.alerts import list_alerts

    alerts = _make_alert(3)  # items on page 2

    db = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 23
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = alerts

    db.execute.side_effect = [count_result, items_result]

    result = await list_alerts(unread_only=False, page=2, page_size=10, db=db, _=None)

    assert result.total == 23
    assert result.page == 2
    assert result.pages == math.ceil(23 / 10)
    assert len(result.items) == 3


@pytest.mark.asyncio
async def test_list_alerts_unread_only():
    from src.api.routers.alerts import list_alerts

    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [count_result, items_result]

    result = await list_alerts(unread_only=True, page=1, page_size=20, db=db, _=None)

    assert result.total == 0
    assert result.pages == 1


@pytest.mark.asyncio
async def test_list_documents_returns_page_schema():
    from src.api.routers.documents import list_documents

    docs = [MagicMock() for _ in range(4)]

    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 4
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = docs
    db.execute.side_effect = [count_result, items_result]

    result = await list_documents(source=None, page=1, page_size=20, db=db)

    assert isinstance(result, Page)
    assert result.total == 4
    assert len(result.items) == 4


@pytest.mark.asyncio
async def test_list_documents_with_source_filter():
    from src.api.routers.documents import list_documents

    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    db.execute.side_effect = [count_result, items_result]

    result = await list_documents(source="cnbv", page=1, page_size=20, db=db)

    assert result.total == 2
    # Two db.execute calls: count + items
    assert db.execute.call_count == 2


# ── Rate limit middleware ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_blocks_after_max_requests():
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Route
    from src.api.middleware.rate_limit import IngestRateLimitMiddleware

    async def ingest_endpoint(request):
        return Response("ok", status_code=202)

    app = Starlette(routes=[Route("/api/v1/ingest/cnbv", ingest_endpoint, methods=["POST"])])
    app.add_middleware(IngestRateLimitMiddleware, max_requests=3, window_seconds=60)

    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(3):
        resp = client.post("/api/v1/ingest/cnbv")
        assert resp.status_code == 202

    # Fourth request should be rate-limited
    resp = client.post("/api/v1/ingest/cnbv")
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_does_not_apply_to_get():
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Route
    from src.api.middleware.rate_limit import IngestRateLimitMiddleware

    async def sources_endpoint(request):
        return Response("ok", status_code=200)

    app = Starlette(routes=[Route("/api/v1/ingest/sources", sources_endpoint, methods=["GET"])])
    app.add_middleware(IngestRateLimitMiddleware, max_requests=2, window_seconds=60)

    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(5):
        resp = client.get("/api/v1/ingest/sources")
        assert resp.status_code == 200
