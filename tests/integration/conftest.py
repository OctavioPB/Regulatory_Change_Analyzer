"""Integration fixtures: real PostgreSQL + pgvector, the real ASGI app, no mocks of the DB.

Run with:
    DATABASE_URL=postgresql+asyncpg://rca_user:rca_pass@localhost:5432/regulatory_test \
    python -m pytest -m integration

Safety: every test TRUNCATEs all tables, so the target database name must end in
``_test``. The suite is skipped entirely when DATABASE_URL does not point at one.

The embedding model is disabled (it would download ~90 MB and makes results
non-deterministic); impact mapping then runs through the rules engine, and
RAG retrieval through the text-search fallback.
"""
import os
import sys
from urllib.parse import urlparse

import pytest

_DB_URL = os.environ.get("DATABASE_URL", "")
_DB_NAME = urlparse(_DB_URL).path.lstrip("/")


def pytest_collection_modifyitems(config, items):
    if _DB_NAME.endswith("_test"):
        return
    skip = pytest.mark.skip(reason="integration tests need DATABASE_URL pointing at a *_test database")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _no_embeddings_no_llm(monkeypatch):
    # Any lazy `from src.mapping.embedder import ...` now raises ImportError,
    # which every caller already treats as "embeddings unavailable".
    monkeypatch.setitem(sys.modules, "src.mapping.embedder", None)
    import src.services.impact_service as impact_service
    import src.services.nlp_service as nlp_service
    from src.config import settings

    monkeypatch.setattr(nlp_service, "_HAS_EMBEDDER", False)
    monkeypatch.setattr(impact_service, "_HAS_SEMANTIC", False)
    # Never spend real tokens from a developer's .env during tests
    monkeypatch.setattr(settings, "anthropic_api_key", "")


@pytest.fixture
async def db_ready():
    from sqlalchemy import text

    from src.database import Base, engine, init_db

    await init_db()
    yield
    async with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    # Pooled asyncpg connections are bound to this test's event loop
    await engine.dispose()


@pytest.fixture
async def client(db_ready):
    import httpx

    from src.api.main import app

    # ASGITransport awaits the whole ASGI call, so BackgroundTasks have finished
    # by the time a request returns — the pipeline is deterministic in tests.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def session(db_ready):
    from src.database import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        yield s
