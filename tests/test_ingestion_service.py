"""
Integration tests for the ingestion service pipeline.
All network calls and DB calls are mocked — no real I/O needed.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.services.ingestion_service as svc
from src.ingestion.base import RawDocument
from src.services.ingestion_service import IngestionResult, _fetch_content, run


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_raw_doc(**overrides) -> RawDocument:
    defaults = dict(
        external_id="CNBV-abc123",
        source="CNBV",
        title="Circular CNBV 5/2025",
        url="https://www.dof.gob.mx/nota_detalle.php?codigo=5756789",
        publication_date=datetime(2025, 3, 20),
        raw_text="Texto del RSS como fallback.",
    )
    defaults.update(overrides)
    return RawDocument(**defaults)


def _make_mock_scraper(fetch_latest_return=None, fetch_text_return="") -> MagicMock:
    """Build a scraper mock whose async methods are properly set up."""
    instance = MagicMock()
    instance.fetch_latest = AsyncMock(return_value=fetch_latest_return or [])
    instance.fetch_document_text = AsyncMock(return_value=fetch_text_return)
    instance.close = AsyncMock()
    instance._get = AsyncMock()
    return instance


# ── run() — top-level pipeline ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_unknown_source_raises():
    db = AsyncMock()
    with pytest.raises(ValueError, match="Unknown source"):
        await run("unknown_source", db)


@pytest.mark.asyncio
async def test_run_returns_ingestion_result_on_scraper_failure():
    """If fetch_latest() raises, run() captures the error and returns normally."""
    db = AsyncMock()
    mock_scraper = _make_mock_scraper()
    mock_scraper.fetch_latest = AsyncMock(side_effect=RuntimeError("network error"))

    MockClass = MagicMock(return_value=mock_scraper)
    with patch.dict(svc._SCRAPERS, {"cnbv": MockClass}):
        result = await run("cnbv", db)

    assert isinstance(result, IngestionResult)
    assert result.fetched == 0
    assert result.new == 0
    assert len(result.errors) == 1
    assert "network error" in result.errors[0]


@pytest.mark.asyncio
async def test_run_skips_existing_documents():
    """Documents already in the DB are counted as skipped."""
    db = AsyncMock()
    raw_doc = _make_raw_doc()
    mock_scraper = _make_mock_scraper(fetch_latest_return=[raw_doc])

    MockClass = MagicMock(return_value=mock_scraper)
    with (
        patch.dict(svc._SCRAPERS, {"cnbv": MockClass}),
        patch.object(svc.document_repo, "get_by_external_id", new=AsyncMock(return_value=MagicMock())),
    ):
        result = await run("cnbv", db)

    assert result.fetched == 1
    assert result.skipped == 1
    assert result.new == 0


@pytest.mark.asyncio
async def test_run_creates_new_document_with_text():
    """New documents with text get persisted."""
    db = AsyncMock()
    raw_doc = _make_raw_doc(raw_text="Texto del reglamento CNBV.")
    mock_scraper = _make_mock_scraper(
        fetch_latest_return=[raw_doc],
        fetch_text_return="Texto completo de la página.",
    )
    mock_create = AsyncMock()

    MockClass = MagicMock(return_value=mock_scraper)
    with (
        patch.dict(svc._SCRAPERS, {"cnbv": MockClass}),
        patch.object(svc.document_repo, "get_by_external_id", new=AsyncMock(return_value=None)),
        patch.object(svc.document_repo, "create_from_raw", new=mock_create),
        patch("src.services.ingestion_service.save_raw_file"),
        patch("src.services.ingestion_service.save_processed_text"),
    ):
        result = await run("cnbv", db)

    assert result.new == 1
    assert result.failed == 0
    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_run_counts_failed_when_no_text():
    """Documents for which no text can be retrieved are counted as failed."""
    db = AsyncMock()
    raw_doc = _make_raw_doc(raw_text=None, url="https://example.com/doc")
    mock_scraper = _make_mock_scraper(
        fetch_latest_return=[raw_doc],
        fetch_text_return="",
    )
    mock_scraper._get = AsyncMock(side_effect=RuntimeError("timeout"))

    MockClass = MagicMock(return_value=mock_scraper)
    with (
        patch.dict(svc._SCRAPERS, {"cnbv": MockClass}),
        patch.object(svc.document_repo, "get_by_external_id", new=AsyncMock(return_value=None)),
        patch("src.services.ingestion_service.save_raw_file"),
        patch("src.services.ingestion_service.save_processed_text"),
    ):
        result = await run("cnbv", db)

    assert result.failed == 1
    assert result.new == 0


# ── _fetch_content() ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_content_uses_rss_fallback_when_html_fails():
    """If HTML fetch returns empty, raw_text from the RSS summary is returned."""
    raw_doc = _make_raw_doc(raw_text="Resumen del RSS.")
    scraper = _make_mock_scraper(fetch_text_return="")
    scraper._get = AsyncMock(side_effect=RuntimeError("timeout"))

    with patch("src.services.ingestion_service.save_processed_text"):
        text, _ = await _fetch_content(scraper, raw_doc)

    assert text == "Resumen del RSS."


@pytest.mark.asyncio
async def test_fetch_content_prefers_html_over_rss():
    """If HTML fetch returns text, it takes priority over the RSS summary."""
    raw_doc = _make_raw_doc(raw_text="Resumen corto.", url="https://example.com/doc")
    scraper = _make_mock_scraper(fetch_text_return="Texto completo y detallado de la página.")

    with (
        patch("src.services.ingestion_service.save_raw_file"),
        patch("src.services.ingestion_service.save_processed_text"),
    ):
        text, _ = await _fetch_content(scraper, raw_doc)

    assert text == "Texto completo y detallado de la página."


@pytest.mark.asyncio
async def test_fetch_content_handles_pdf_url():
    """URLs ending in .pdf trigger the PDF parser path."""
    raw_doc = _make_raw_doc(url="https://example.com/circular.pdf", raw_text=None)
    scraper = _make_mock_scraper()
    mock_response = MagicMock()
    mock_response.content = b"%PDF-fake-bytes"
    scraper._get = AsyncMock(return_value=mock_response)

    saved_path = Path("data/raw/cnbv/test.pdf")

    with (
        patch("src.services.ingestion_service.extract_text_from_pdf_bytes", return_value="Texto del PDF"),
        patch("src.services.ingestion_service.save_raw_file", return_value=saved_path),
        patch("src.services.ingestion_service.save_processed_text"),
    ):
        text, path = await _fetch_content(scraper, raw_doc)

    assert text == "Texto del PDF"
    assert path == str(saved_path)
    scraper.fetch_document_text.assert_not_called()
