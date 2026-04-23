import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

import feedparser

from src.ingestion.base import RawDocument
from src.ingestion.cnbv import CNBVScraper
from src.ingestion.sec import SECScraper


# ── CNBVScraper static helpers ────────────────────────────────────────────────

def test_cnbv_is_cnbv_entry_positive():
    assert CNBVScraper._is_cnbv_entry("Circular CNBV 10/2025 - Fintech") is True


def test_cnbv_is_cnbv_entry_sofom():
    assert CNBVScraper._is_cnbv_entry("Disposiciones para SOFOM reguladas") is True


def test_cnbv_is_cnbv_entry_negative():
    assert CNBVScraper._is_cnbv_entry("Decreto presidencial sobre aranceles") is False


def test_cnbv_parse_date_valid():
    date = CNBVScraper._parse_date("Mon, 20 Mar 2025 00:00:00 +0000")
    assert date is not None
    assert date.year == 2025
    assert date.month == 3


def test_cnbv_parse_date_gmt():
    date = CNBVScraper._parse_date("Mon, 20 Mar 2025 00:00:00 GMT")
    assert date is not None


def test_cnbv_parse_date_invalid_returns_none():
    assert CNBVScraper._parse_date("not a date") is None


def test_cnbv_parse_date_empty_returns_none():
    assert CNBVScraper._parse_date("") is None


# ── CNBVScraper.fetch_latest() ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cnbv_fetch_latest_filters_non_cnbv_entries(sample_cnbv_rss):
    scraper = CNBVScraper()
    with patch.object(scraper, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.text = sample_cnbv_rss
        docs = await scraper.fetch_latest()

    # Only the CNBV entry should pass the filter; the "política exterior" one should not
    assert len(docs) == 1
    assert "CNBV" in docs[0].title or "Circular" in docs[0].title
    await scraper.close()


@pytest.mark.asyncio
async def test_cnbv_fetch_latest_external_id_is_stable(sample_cnbv_rss):
    """Same feed → same external_id (hash is deterministic)."""
    scraper = CNBVScraper()
    with patch.object(scraper, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.text = sample_cnbv_rss
        docs1 = await scraper.fetch_latest()
        docs2 = await scraper.fetch_latest()

    assert docs1[0].external_id == docs2[0].external_id
    await scraper.close()


@pytest.mark.asyncio
async def test_cnbv_fetch_latest_populates_raw_text_from_rss(sample_cnbv_rss):
    scraper = CNBVScraper()
    with patch.object(scraper, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.text = sample_cnbv_rss
        docs = await scraper.fetch_latest()

    assert docs[0].raw_text is not None
    assert len(docs[0].raw_text) > 0
    await scraper.close()


@pytest.mark.asyncio
async def test_cnbv_fetch_latest_returns_empty_on_error():
    scraper = CNBVScraper()
    with patch.object(scraper, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = RuntimeError("network error")
        docs = await scraper.fetch_latest()

    assert docs == []
    await scraper.close()


# ── SECScraper static helpers ─────────────────────────────────────────────────

def test_sec_is_rule_entry_final_rule():
    assert SECScraper._is_rule_entry("SEC Adopts Final Rule on X", "") is True


def test_sec_is_rule_entry_proposed_rule():
    assert SECScraper._is_rule_entry("SEC Proposes Rule on Y", "") is True


def test_sec_is_rule_entry_in_summary():
    assert SECScraper._is_rule_entry("Announcement", "Commission adopts final rule amending Reg S-K") is True


def test_sec_is_rule_entry_enforcement_excluded():
    assert SECScraper._is_rule_entry("SEC Charges Company with Fraud", "Enforcement action") is False


def test_sec_parse_date_rss_format():
    date = SECScraper._parse_date("Mon, 20 Jan 2025 12:00:00 GMT")
    assert date is not None
    assert date.month == 1


def test_sec_parse_date_iso_format():
    date = SECScraper._parse_date("2025-03-20T12:00:00+00:00")
    assert date is not None
    assert date.month == 3


# ── SECScraper.fetch_latest() ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sec_fetch_latest_filters_non_rule_entries(sample_sec_rss):
    scraper = SECScraper()
    with patch.object(scraper, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.text = sample_sec_rss
        docs = await scraper.fetch_latest()

    # Only the "Final Rule" entry should pass; the fraud enforcement one should not
    assert len(docs) == 1
    assert "Final Rule" in docs[0].title or "rule" in docs[0].title.lower()
    await scraper.close()


@pytest.mark.asyncio
async def test_sec_fetch_latest_returns_empty_on_error():
    scraper = SECScraper()
    with patch.object(scraper, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = RuntimeError("timeout")
        docs = await scraper.fetch_latest()

    assert docs == []
    await scraper.close()


# ── RawDocument dataclass ─────────────────────────────────────────────────────

def test_raw_document_optional_fields_default_to_none():
    doc = RawDocument(
        external_id="TEST-001",
        source="CNBV",
        title="Test",
        url="https://example.com",
        publication_date=datetime(2025, 1, 1),
    )
    assert doc.raw_text is None
    assert doc.file_path is None
