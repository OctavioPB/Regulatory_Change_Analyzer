import pytest

from src.models.document import ChangeType
from src.models.impact import Severity
from src.recommendations.generator import generate_suggestion


def test_generate_suggestion_limit_modification_high():
    suggestion = generate_suggestion(
        change_type=ChangeType.limit_modification,
        severity=Severity.high,
        clause_ref="Clause 4.2",
        article_ref="Article 5",
        source_title="Circular CNBV 10/2025",
    )
    assert "Clause 4.2" in suggestion
    assert "Article 5" in suggestion
    assert "UPDATE REQUIRED" in suggestion


def test_generate_suggestion_repeal_high():
    suggestion = generate_suggestion(
        change_type=ChangeType.repeal,
        severity=Severity.high,
        clause_ref="Clause 7.1",
        article_ref="Article 12",
        source_title="SEC Rule 2025-01",
    )
    assert "OBSOLETE" in suggestion or "repealed" in suggestion.lower()


def test_generate_suggestion_fallback_for_unknown_combination():
    suggestion = generate_suggestion(
        change_type=ChangeType.other,
        severity=Severity.low,
        clause_ref="Clause X",
        article_ref="Article Y",
        source_title="Some Regulation",
    )
    assert "MANUAL REVIEW" in suggestion
    assert "Clause X" in suggestion


def test_generate_suggestion_returns_non_empty_string():
    result = generate_suggestion(
        change_type=ChangeType.clarification,
        severity=Severity.medium,
        clause_ref="",
        article_ref="",
        source_title="Regulation ABC",
    )
    assert isinstance(result, str)
    assert len(result) > 10
