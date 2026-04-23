"""Tests for the impact mapping service."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.document import ChangeType
from src.models.impact import ImpactAlert, ImpactItem, Severity
from src.services.impact_service import (
    ImpactResult,
    _max_severity,
    map_change_to_contracts,
    map_document_impacts,
)
from src.mapping.rules_engine import RuleMatch


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_change(
    change_type: ChangeType = ChangeType.limit_modification,
    new_text: str = "El límite para SOFOM es del 15%.",
    summary: str = "Artículo 5: límite reducido de 20% a 15%",
) -> MagicMock:
    change = MagicMock()
    change.id = uuid.uuid4()
    change.document_id = uuid.uuid4()
    change.change_type = change_type
    change.new_text = new_text
    change.summary = summary
    change.article_ref = "Artículo 5"

    doc = MagicMock()
    doc.id = change.document_id
    doc.title = "Circular CNBV 10/2025"
    change.document = doc
    return change


def _make_contract(name: str, contract_type: str, area: str) -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.name = name
    c.contract_type = contract_type
    c.area = area
    return c


def _make_alert() -> MagicMock:
    alert = MagicMock(spec=ImpactAlert)
    alert.id = uuid.uuid4()
    return alert


# ── map_change_to_contracts ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_map_change_returns_not_found_for_missing_id():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    result = await map_change_to_contracts(uuid.uuid4(), db)

    assert result.skipped is True
    assert result.error == "Change not found"
    assert result.alerts_created == 0


@pytest.mark.asyncio
async def test_map_change_skips_when_no_text():
    change = _make_change(new_text="", summary="")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=change)))

    result = await map_change_to_contracts(change.id, db)

    assert result.skipped is True


@pytest.mark.asyncio
async def test_map_change_skips_when_no_targets():
    change = _make_change(new_text="Texto sin keywords relevantes ni contratos similares.")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=change)))

    with (
        patch("src.services.impact_service._HAS_SEMANTIC", False),
        patch("src.services.impact_service.apply_rules", return_value=[]),
        patch("src.services.impact_service.contract_repo.get_by_types_or_areas",
              new_callable=AsyncMock, return_value=[]),
    ):
        result = await map_change_to_contracts(change.id, db)

    assert result.skipped is True
    assert result.alerts_created == 0


@pytest.mark.asyncio
async def test_map_change_creates_alert_and_items_via_rules():
    """Rules engine fires → matching contracts found → alert + items created."""
    change = _make_change(new_text="Las SOFOM deben ajustar sus límites de crédito.")
    loan_contract = _make_contract("Master Loan Agreement - Fintech ABC", "loan", "Risk")
    alert = _make_alert()
    item = MagicMock(spec=ImpactItem)

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=change)))
    db.commit = AsyncMock()

    rule_match = RuleMatch(
        rule_id="R001",
        contract_types=["loan", "credit"],
        areas=["Risk"],
        severity=Severity.high,
        description="SOFOM rule",
        matched_keyword=r"\bSOFOM\b",
    )

    with (
        patch("src.services.impact_service._HAS_SEMANTIC", False),
        patch("src.services.impact_service.apply_rules", return_value=[rule_match]),
        patch("src.services.impact_service.contracts_targeted_by_rules",
              return_value=({"loan", "credit"}, {"Risk"})),
        patch("src.services.impact_service.contract_repo.get_by_types_or_areas",
              new_callable=AsyncMock, return_value=[loan_contract]),
        patch("src.services.impact_service.impact_repo.create_alert",
              new_callable=AsyncMock, return_value=alert),
        patch("src.services.impact_service.impact_repo.create_item",
              new_callable=AsyncMock, return_value=item),
    ):
        result = await map_change_to_contracts(change.id, db)

    assert result.skipped is False
    assert result.alerts_created == 1
    assert result.items_created == 1


@pytest.mark.asyncio
async def test_map_change_deduplicates_rule_contracts_already_in_clause_matches():
    """Contracts already covered by clause matches are NOT double-counted via rules."""
    change = _make_change(new_text="El límite para SOFOM se reduce al 15%.")
    alert = _make_alert()
    item = MagicMock(spec=ImpactItem)

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=change)))
    db.commit = AsyncMock()

    # Clause match covers "Master Loan Agreement"
    clause_match = MagicMock()
    clause_match.clause_id = uuid.uuid4()
    clause_match.clause_ref = "Clause 4.2"
    clause_match.contract_name = "Master Loan Agreement"
    clause_match.similarity = 0.85
    clause_match.severity = Severity.high

    # Rule also targets "Master Loan Agreement" via contract type
    same_contract = _make_contract("Master Loan Agreement", "loan", "Risk")

    rule_match = RuleMatch(
        rule_id="R001",
        contract_types=["loan"],
        areas=["Risk"],
        severity=Severity.high,
        description="SOFOM",
        matched_keyword=r"\bSOFOM\b",
    )

    with (
        patch("src.services.impact_service._HAS_SEMANTIC", True),
        patch("src.services.impact_service.find_similar_clauses",
              new_callable=AsyncMock, return_value=[clause_match]),
        patch("src.services.impact_service.apply_rules", return_value=[rule_match]),
        patch("src.services.impact_service.contracts_targeted_by_rules",
              return_value=({"loan"}, {"Risk"})),
        patch("src.services.impact_service.contract_repo.get_by_types_or_areas",
              new_callable=AsyncMock, return_value=[same_contract]),
        patch("src.services.impact_service.impact_repo.create_alert",
              new_callable=AsyncMock, return_value=alert),
        patch("src.services.impact_service.impact_repo.create_item",
              new_callable=AsyncMock, return_value=item),
    ):
        result = await map_change_to_contracts(change.id, db)

    # Only 1 item created (clause match), rule contract deduplicated
    assert result.items_created == 1


# ── map_document_impacts ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_map_document_returns_empty_result_for_no_changes():
    doc_id = uuid.uuid4()
    db = AsyncMock()
    # DB returns empty scalars
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))

    result = await map_document_impacts(doc_id, db)

    assert result.changes_processed == 0
    assert result.alerts_created == 0
    assert result.items_created == 0


@pytest.mark.asyncio
async def test_map_document_aggregates_across_changes():
    doc_id = uuid.uuid4()
    change1_id = uuid.uuid4()
    change2_id = uuid.uuid4()

    c1 = MagicMock()
    c1.id = change1_id
    c2 = MagicMock()
    c2.id = change2_id

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[c1, c2])))
        )
    )

    async def mock_map_change(change_id, db):
        return ImpactResult(change_id=change_id, alerts_created=1, items_created=2)

    with patch("src.services.impact_service.map_change_to_contracts", side_effect=mock_map_change):
        result = await map_document_impacts(doc_id, db)

    assert result.changes_processed == 2
    assert result.alerts_created == 2
    assert result.items_created == 4
    assert result.errors == []


@pytest.mark.asyncio
async def test_map_document_skipped_changes_not_counted():
    doc_id = uuid.uuid4()
    change_id = uuid.uuid4()
    c = MagicMock()
    c.id = change_id

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[c])))
        )
    )

    async def mock_map_skipped(change_id, db):
        return ImpactResult(change_id=change_id, skipped=True)

    with patch("src.services.impact_service.map_change_to_contracts", side_effect=mock_map_skipped):
        result = await map_document_impacts(doc_id, db)

    assert result.changes_processed == 0
    assert result.alerts_created == 0


# ── _max_severity ─────────────────────────────────────────────────────────────

def _rule(severity: Severity) -> RuleMatch:
    return RuleMatch(
        rule_id="X", contract_types=[], areas=[],
        severity=severity, description="", matched_keyword=""
    )


def test_max_severity_returns_high_when_present():
    matches = [_rule(Severity.low), _rule(Severity.high), _rule(Severity.medium)]
    assert _max_severity(matches) == Severity.high


def test_max_severity_returns_medium_when_no_high():
    matches = [_rule(Severity.low), _rule(Severity.medium)]
    assert _max_severity(matches) == Severity.medium


def test_max_severity_returns_low_for_single_low():
    assert _max_severity([_rule(Severity.low)]) == Severity.low


def test_max_severity_returns_low_for_empty():
    from src.services.impact_service import _max_severity
    assert _max_severity([]) == Severity.low
