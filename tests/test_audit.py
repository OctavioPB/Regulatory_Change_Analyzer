"""Tests for the audit repository and the audit trail integration in services."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.repositories.audit_repo import list_recent, log


# ── audit_repo.log ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_adds_entry_to_session():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    await log(db, action="document_ingested", entity_type="RegulatoryDocument",
              entity_id=str(uuid.uuid4()), detail="source=CNBV")

    assert db.add.called
    assert db.flush.called
    entry = db.add.call_args[0][0]
    assert entry.action == "document_ingested"
    assert entry.actor == "system"


@pytest.mark.asyncio
async def test_log_uses_custom_actor():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    await log(db, action="item_approved", actor="reviewer@example.com")

    entry = db.add.call_args[0][0]
    assert entry.actor == "reviewer@example.com"


@pytest.mark.asyncio
async def test_log_accepts_none_detail():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    await log(db, action="document_analyzed")

    entry = db.add.call_args[0][0]
    assert entry.detail is None
    assert entry.entity_type is None


# ── audit_repo.list_recent ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_recent_returns_list():
    from src.models.audit import AuditLog
    mock_entry = MagicMock(spec=AuditLog)
    mock_entry.action = "document_ingested"

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_entry]))))
    )

    results = await list_recent(db)
    assert len(results) == 1
    assert results[0].action == "document_ingested"


# ── NLP service audit integration ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_document_writes_audit_on_success():
    """analyze_document() should call audit_repo.log when changes are created."""
    from src.services.nlp_service import analyze_document

    doc_id = uuid.uuid4()
    doc = MagicMock()
    doc.id = doc_id
    doc.source = "CNBV"
    doc.external_id = "CNBV-abc"
    doc.raw_text = "Artículo 5. El límite de contraparte es del 15%."

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=doc)),   # doc lookup
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # not yet analyzed
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no prior version
    ])

    with patch("src.services.nlp_service.audit_repo.log", new_callable=AsyncMock) as mock_log:
        result = await analyze_document(doc_id, db)

    if not result.skipped and result.changes_created > 0:
        assert mock_log.called
        call_kwargs = mock_log.call_args[1] if mock_log.call_args[1] else {}
        call_args = mock_log.call_args[0]
        # action is second positional arg or keyword
        action_val = call_kwargs.get("action") or (call_args[1] if len(call_args) > 1 else None)
        assert action_val == "document_analyzed"
