import logging
from string import Template

from src.models.document import ChangeType
from src.models.impact import Severity

logger = logging.getLogger(__name__)

# Suggestion templates keyed by (change_type, severity)
_TEMPLATES: dict[tuple[ChangeType, Severity], str] = {
    (ChangeType.limit_modification, Severity.high): (
        "UPDATE REQUIRED (HIGH): In $clause_ref, replace the current numeric limit with "
        "the value specified in $article_ref of $source_title. "
        "Verify that all downstream calculations and system thresholds are adjusted accordingly."
    ),
    (ChangeType.limit_modification, Severity.medium): (
        "REVIEW RECOMMENDED: $clause_ref references a limit that may be affected by "
        "$article_ref of $source_title. Confirm whether the new value applies to this contract."
    ),
    (ChangeType.new_requirement, Severity.high): (
        "NEW CLAUSE NEEDED (HIGH): $source_title introduces a new obligation in $article_ref. "
        "Add a clause to $clause_ref reflecting this requirement. Consult legal counsel."
    ),
    (ChangeType.new_requirement, Severity.medium): (
        "POTENTIAL GAP: $source_title adds a requirement in $article_ref that may not be "
        "covered by the current text of $clause_ref. Manual review recommended."
    ),
    (ChangeType.repeal, Severity.high): (
        "CLAUSE OBSOLETE (HIGH): The provision referenced in $clause_ref has been repealed "
        "by $article_ref of $source_title. Remove or replace this clause immediately."
    ),
    (ChangeType.deadline, Severity.high): (
        "DEADLINE CHANGE (HIGH): $article_ref of $source_title modifies a deadline relevant "
        "to $clause_ref. Update the date in the contract and notify all stakeholders."
    ),
}

_DEFAULT_TEMPLATE = (
    "MANUAL REVIEW REQUIRED: $source_title contains a change in $article_ref that may "
    "affect $clause_ref. Severity: $severity. Assess and adjust as needed."
)


def generate_suggestion(
    change_type: ChangeType,
    severity: Severity,
    clause_ref: str,
    article_ref: str,
    source_title: str,
) -> str:
    """Generate a human-readable suggestion for a detected impact.

    Args:
        change_type: The type of regulatory change.
        severity: Impact severity determined by semantic similarity.
        clause_ref: Identifier of the affected contract clause.
        article_ref: Regulatory article that triggered the change.
        source_title: Title of the regulatory document.

    Returns:
        A formatted suggestion string ready for display in the dashboard.
    """
    template_str = _TEMPLATES.get((change_type, severity), _DEFAULT_TEMPLATE)
    suggestion = Template(template_str).safe_substitute(
        clause_ref=clause_ref or "unspecified clause",
        article_ref=article_ref or "unspecified article",
        source_title=source_title,
        severity=severity.value,
    )
    logger.debug("Generated suggestion for %s/%s: %s", change_type.value, severity.value, suggestion[:80])
    return suggestion
