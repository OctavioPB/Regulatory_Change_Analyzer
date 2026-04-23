"""Tests for the DB-integrated NLP service."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.nlp_service import NlpResult, analyze_all_pending, analyze_document


def _make_doc(**overrides):
    """Build a minimal RegulatoryDocument mock."""
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.source = "CNBV"
    doc.external_id = "CNBV-abc123"
    doc.publication_date = datetime(2025, 3, 20)
    doc.raw_text = (
        "Artículo 5. El límite de contraparte es del 15%.\n\n"
        "Artículo 6. Los plazos serán de 30 días hábiles."
    )
    for k, v in overrides.items():
        setattr(doc, k, v)
    return doc


# ── analyze_document ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_document_returns_not_found_for_missing_id():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    result = await analyze_document(uuid.uuid4(), db)

    assert result.error == "Document not found"
    assert result.changes_created == 0


@pytest.mark.asyncio
async def test_analyze_document_skips_when_no_text():
    doc = _make_doc(raw_text=None)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=doc)))

    result = await analyze_document(doc.id, db)

    assert result.skipped is True
    assert "No raw text" in (result.error or "")


@pytest.mark.asyncio
async def test_analyze_document_skips_already_analyzed():
    doc = _make_doc()
    existing_change_id = uuid.uuid4()

    execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=doc)),       # document lookup
        MagicMock(scalar_one_or_none=MagicMock(return_value=existing_change_id)),  # already analyzed check
    ]
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute_results)

    result = await analyze_document(doc.id, db)

    assert result.skipped is True


@pytest.mark.asyncio
async def test_analyze_document_creates_changes_for_new_document():
    """A document with no prior version should produce at least one change record."""
    doc = _make_doc()

    execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=doc)),   # document lookup
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # not yet analyzed
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no previous version
    ]
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute_results)
    db.add = MagicMock()

    result = await analyze_document(doc.id, db)

    assert result.skipped is False
    assert result.changes_created >= 1
    assert db.add.called


@pytest.mark.asyncio
async def test_analyze_document_uses_prior_version_when_available():
    """When a prior version exists, analyze() receives old_text and can detect diffs."""
    doc = _make_doc()
    old_text = "Artículo 5. El límite de contraparte es del 20%."

    execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=doc)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),   # not yet analyzed
        MagicMock(scalar_one_or_none=MagicMock(return_value=old_text)),  # prior version found
    ]
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute_results)
    db.add = MagicMock()

    with patch("src.services.nlp_service.analyze") as mock_analyze:
        mock_result = MagicMock()
        mock_result.has_changes = True
        mock_result.changes = [MagicMock()]
        mock_analyze.return_value = mock_result

        await analyze_document(doc.id, db)

    # Verify analyze() was called with both texts
    call_args = mock_analyze.call_args
    assert call_args[0][0] == doc.raw_text   # new_text
    assert call_args[0][1] == old_text        # old_text


# ── analyze_all_pending ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_all_pending_returns_aggregate_counts():
    """Aggregate totals are correctly summed across multiple documents."""
    doc1 = _make_doc()
    doc2 = _make_doc()

    async def mock_analyze_document(doc_id, db):
        return NlpResult(document_id=doc_id, changes_created=3)

    db = AsyncMock()
    docs_result = MagicMock()
    docs_result.scalars.return_value.all.return_value = [doc1, doc2]
    db.execute = AsyncMock(return_value=docs_result)

    with patch("src.services.nlp_service.analyze_document", side_effect=mock_analyze_document):
        totals = await analyze_all_pending(db)

    assert totals["analyzed"] == 2
    assert totals["changes_created"] == 6
    assert totals["errors"] == 0


@pytest.mark.asyncio
async def test_analyze_all_pending_counts_errors():
    doc = _make_doc()

    async def mock_error(doc_id, db):
        return NlpResult(document_id=doc_id, error="NLP failure", skipped=False)

    db = AsyncMock()
    docs_result = MagicMock()
    docs_result.scalars.return_value.all.return_value = [doc]
    db.execute = AsyncMock(return_value=docs_result)

    with patch("src.services.nlp_service.analyze_document", side_effect=mock_error):
        totals = await analyze_all_pending(db)

    assert totals["errors"] == 1
    assert totals["analyzed"] == 0
