"""Tests for multi-jurisdictional cross-mapping."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mapping.cross_mapper import CrossCandidate, _build_analysis, _RULE_DESCRIPTIONS
from src.models.document import ChangeType


# ── Helper builders ───────────────────────────────────────────────────────────

def _make_change(
    summary: str,
    new_text: str = "",
    embedding: list[float] | None = None,
    source: str = "SEC",
) -> MagicMock:
    from src.models.document import RegulatoryChange
    change = MagicMock(spec=RegulatoryChange)
    change.id = uuid.uuid4()
    change.summary = summary
    change.new_text = new_text
    change.old_text = None
    change.article_ref = "Art. 1"
    change.change_type = ChangeType.limit_modification
    change.embedding = embedding

    doc = MagicMock()
    doc.source = source
    doc.title = f"{source} Regulation"
    change.document = doc
    return change


# ── _build_analysis ───────────────────────────────────────────────────────────

def test_build_analysis_contains_jurisdictions():
    source = _make_change("Capital adequacy rule updated", source="SEC")
    target = _make_change("Coeficiente de capitalización CNBV", source="CNBV")
    analysis = _build_analysis(source, "SEC", target, "CNBV", 0.82, ["R007"])
    assert "SEC" in analysis
    assert "CNBV" in analysis
    assert "R007" in analysis


def test_build_analysis_high_similarity_label():
    source = _make_change("Leverage limit", source="SEC")
    target = _make_change("Límite de apalancamiento", source="CNBV")
    analysis = _build_analysis(source, "SEC", target, "CNBV", 0.80, ["R007"])
    assert "high" in analysis


def test_build_analysis_moderate_similarity_label():
    source = _make_change("AML reporting", source="SEC")
    target = _make_change("Reporte PLD", source="CNBV")
    analysis = _build_analysis(source, "SEC", target, "CNBV", 0.65, ["R003"])
    assert "moderate" in analysis


def test_build_analysis_rules_only_label():
    source = _make_change("SOFOM credit", source="CNBV")
    target = _make_change("Loan disclosure", source="SEC")
    analysis = _build_analysis(source, "CNBV", target, "SEC", 0.0, ["R001"])
    # similarity=0.0 → rules-only path, no similarity percentage shown
    assert "shared regulatory domain" in analysis
    assert "Semantic similarity" not in analysis


def test_build_analysis_includes_rule_description():
    source = _make_change("Capital rule", source="SEC")
    target = _make_change("Capital", source="CNBV")
    analysis = _build_analysis(source, "SEC", target, "CNBV", 0.70, ["R007"])
    expected_desc = _RULE_DESCRIPTIONS["R007"]
    assert expected_desc in analysis


def test_build_analysis_multiple_shared_rules():
    source = _make_change("AML + capital", source="SEC")
    target = _make_change("PLD + capital", source="CNBV")
    analysis = _build_analysis(source, "SEC", target, "CNBV", 0.72, ["R003", "R007"])
    assert "R003" in analysis
    assert "R007" in analysis


# ── find_cross_links (mocked DB) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_cross_links_no_rules_returns_empty():
    """A change that fires no rules is skipped — no cross-links possible."""
    from src.mapping.cross_mapper import find_cross_links
    change = _make_change("Quarterly earnings release procedure", source="SEC")
    change.embedding = [0.1] * 384
    db = AsyncMock()
    result = await find_cross_links(change, "SEC", db)
    assert result == []


@pytest.mark.asyncio
async def test_find_cross_links_no_embedding_no_rules_returns_empty():
    """No embedding + no matching rule domain → empty."""
    from src.mapping.cross_mapper import find_cross_links
    change = _make_change("Holiday schedule announcement", source="SEC")
    change.embedding = None
    db = AsyncMock()

    with patch("src.mapping.cross_mapper._rules_only_candidates", new_callable=AsyncMock, return_value=[]):
        result = await find_cross_links(change, "SEC", db)
    assert result == []


@pytest.mark.asyncio
async def test_find_cross_links_with_embedding_candidate_passes_both_stages():
    """A candidate that fires the same rules AND has high similarity is returned."""
    from src.mapping.cross_mapper import find_cross_links

    # Source: SEC change about capital/leverage (fires R007)
    source = _make_change(
        "SEC raises leverage ratio threshold under Basel III",
        new_text="The leverage ratio is increased from 3% to 4% per Basel requirements. Capital coefficients must be adjusted.",
        embedding=[0.5] * 384,
        source="SEC",
    )

    # Target: CNBV change also about capital (fires R007)
    target = _make_change(
        "CNBV modifica coeficiente de capital",
        new_text="Se modifica el coeficiente de capital para alinearse a Basel III. El nuevo límite de apalancamiento es 4%.",
        source="CNBV",
    )
    target.embedding = None  # target doesn't need embedding — we control the candidate list

    db = AsyncMock()

    # Mock Stage 1: embedding search returns (target, similarity=0.82)
    async def mock_embedding_candidates(change, source_jur, db, top_k):
        return [(target, 0.82)]

    with patch("src.mapping.cross_mapper._embedding_candidates", side_effect=mock_embedding_candidates):
        result = await find_cross_links(source, "SEC", db)

    assert len(result) == 1
    link = result[0]
    assert link.source_jurisdiction == "SEC"
    assert link.target_jurisdiction == "CNBV"
    assert link.similarity_score == pytest.approx(0.82, abs=0.01)
    assert "R007" in link.shared_rule_ids


@pytest.mark.asyncio
async def test_find_cross_links_candidate_discarded_no_shared_rules():
    """A high-similarity candidate that fires different rules is discarded."""
    from src.mapping.cross_mapper import find_cross_links

    # Source fires R003 (AML)
    source = _make_change(
        "New AML requirements",
        new_text="Enhanced anti-money laundering (AML) reporting obligations for financial institutions under FATF.",
        embedding=[0.5] * 384,
        source="SEC",
    )

    # Target fires R004 (data privacy) — different domain
    target = _make_change(
        "Data privacy update",
        new_text="Updated personal data privacy and data protection requirements per LFPDPPP.",
        source="CNBV",
    )

    db = AsyncMock()

    async def mock_embedding_candidates(change, source_jur, db, top_k):
        return [(target, 0.90)]  # high similarity but wrong domain

    with patch("src.mapping.cross_mapper._embedding_candidates", side_effect=mock_embedding_candidates):
        result = await find_cross_links(source, "SEC", db)

    # R003 and R004 don't overlap → discarded
    assert result == []


# ── CrossCandidate ────────────────────────────────────────────────────────────

def test_cross_candidate_fields():
    cand = CrossCandidate(
        source_change_id=str(uuid.uuid4()),
        target_change_id=str(uuid.uuid4()),
        source_jurisdiction="SEC",
        target_jurisdiction="CNBV",
        similarity_score=0.78,
        shared_rule_ids=["R001", "R007"],
        analysis="Analysis text.",
    )
    assert cand.source_jurisdiction == "SEC"
    assert "R001" in cand.shared_rule_ids
    assert cand.similarity_score == pytest.approx(0.78)


# ── cross_mapping_repo ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_link_creates_new():
    from src.repositories import cross_mapping_repo

    candidate = CrossCandidate(
        source_change_id=str(uuid.uuid4()),
        target_change_id=str(uuid.uuid4()),
        source_jurisdiction="SEC",
        target_jurisdiction="CNBV",
        similarity_score=0.75,
        shared_rule_ids=["R007"],
        analysis="Analysis.",
    )

    db = AsyncMock()
    # No existing link
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=existing_result)
    db.add = MagicMock()
    db.flush = AsyncMock()

    link = await cross_mapping_repo.upsert_link(db, candidate)

    db.add.assert_called_once()
    db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_link_returns_existing():
    from src.repositories import cross_mapping_repo
    from src.models.cross_mapping import CrossJurisdictionLink

    existing_link = MagicMock(spec=CrossJurisdictionLink)
    existing_link.id = uuid.uuid4()

    candidate = CrossCandidate(
        source_change_id=str(uuid.uuid4()),
        target_change_id=str(uuid.uuid4()),
        source_jurisdiction="SEC",
        target_jurisdiction="CNBV",
        similarity_score=0.75,
        shared_rule_ids=["R007"],
        analysis="Analysis.",
    )

    db = AsyncMock()
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing_link
    db.execute = AsyncMock(return_value=existing_result)

    link = await cross_mapping_repo.upsert_link(db, candidate)

    assert link is existing_link
    db.add.assert_not_called()


# ── cross_mapping_service ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_change_not_found_returns_error():
    from src.services import cross_mapping_service

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    result = await cross_mapping_service.scan_change(uuid.uuid4(), db)
    assert result.skipped is True
    assert result.error == "Change not found"


@pytest.mark.asyncio
async def test_scan_change_no_candidates_creates_zero_links():
    from src.services import cross_mapping_service

    source = _make_change("Capital ratio update", source="SEC")
    source.embedding = [0.1] * 384

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = source
    db.execute = AsyncMock(return_value=result_mock)

    with patch("src.services.cross_mapping_service.find_cross_links", new_callable=AsyncMock, return_value=[]):
        result = await cross_mapping_service.scan_change(source.id, db)

    assert result.links_created == 0
    assert result.skipped is False


@pytest.mark.asyncio
async def test_scan_change_creates_links_for_candidates():
    from src.services import cross_mapping_service
    from src.models.cross_mapping import CrossJurisdictionLink

    source = _make_change("Basel III capital", source="SEC")

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = source
    db.execute = AsyncMock(return_value=result_mock)

    candidate = CrossCandidate(
        source_change_id=str(source.id),
        target_change_id=str(uuid.uuid4()),
        source_jurisdiction="SEC",
        target_jurisdiction="CNBV",
        similarity_score=0.81,
        shared_rule_ids=["R007"],
        analysis="Analysis.",
    )

    mock_link = MagicMock(spec=CrossJurisdictionLink)
    mock_link.id = uuid.uuid4()

    with (
        patch("src.services.cross_mapping_service.find_cross_links", new_callable=AsyncMock, return_value=[candidate]),
        patch("src.services.cross_mapping_service.cross_mapping_repo.upsert_link", new_callable=AsyncMock, return_value=mock_link),
        patch("src.services.cross_mapping_service.audit_repo.log", new_callable=AsyncMock),
    ):
        result = await cross_mapping_service.scan_change(source.id, db)

    assert result.links_created == 1
    assert result.source_jurisdiction == "SEC"


# ── CrossLinkOut schema ───────────────────────────────────────────────────────

def test_cross_link_out_shared_rule_ids_is_json_string():
    from src.api.schemas import CrossLinkOut
    # The field stores a JSON string (from the DB column), not a list
    data = CrossLinkOut(
        id=uuid.uuid4(),
        source_change_id=uuid.uuid4(),
        target_change_id=uuid.uuid4(),
        source_jurisdiction="SEC",
        target_jurisdiction="CNBV",
        similarity_score=0.77,
        shared_rule_ids='["R001","R007"]',
        analysis="Analysis text.",
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    parsed = json.loads(data.shared_rule_ids)
    assert "R001" in parsed
    assert "R007" in parsed
