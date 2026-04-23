import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ingestion.base import BaseScraper, RawDocument
from src.ingestion.cnbv import CNBVScraper
from src.ingestion.sec import SECScraper


def test_cnbv_is_cnbv_entry_positive():
    assert CNBVScraper._is_cnbv_entry("Circular CNBV 10/2025 - Fintech") is True


def test_cnbv_is_cnbv_entry_negative():
    assert CNBVScraper._is_cnbv_entry("Decreto presidencial sobre aranceles") is False


def test_cnbv_parse_date_valid():
    date = CNBVScraper._parse_date("Mon, 20 Mar 2025 00:00:00 +0000")
    assert date is not None
    assert date.year == 2025


def test_cnbv_parse_date_invalid_returns_none():
    assert CNBVScraper._parse_date("not a date") is None


def test_sec_parse_date_iso_format():
    date = SECScraper._parse_date("2025-03-20T12:00:00+00:00")
    assert date is not None
    assert date.month == 3


def test_raw_document_fields():
    from datetime import datetime
    doc = RawDocument(
        external_id="TEST-001",
        source="CNBV",
        title="Test",
        url="https://example.com",
        publication_date=datetime(2025, 1, 1),
    )
    assert doc.source == "CNBV"
    assert doc.raw_text is None
