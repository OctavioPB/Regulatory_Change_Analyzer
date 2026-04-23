import difflib
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────────────

_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})\b"
    r"|\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
    re.IGNORECASE,
)
_ARTICLE_PATTERN = re.compile(
    r"\b(Art[íi]culo|Article|Section|Secci[óo]n|Regla|Rule)\s+(\d+[\w\.]*)\b",
    re.IGNORECASE,
)
_PERCENTAGE_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")
_MONETARY_PATTERN = re.compile(
    r"(?:\$|USD|MXN|EUR)\s*[\d,]+(?:\.\d{2})?|\b[\d,]+(?:\.\d{2})?\s*(?:pesos?|dollars?|euros?)\b",
    re.IGNORECASE,
)
_PENALTY_PATTERN = re.compile(
    r"\b(multa|penalidad|sanci[óo]n|fine|penalty|sanction)\b.{0,150}",
    re.IGNORECASE,
)

# Context window (chars) around a number to use for fuzzy matching
_CONTEXT_WINDOW = 80


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ExtractedEntities:
    """Named entities and key values found in a regulatory text."""

    dates: list[str] = field(default_factory=list)
    articles: list[str] = field(default_factory=list)
    percentages: list[str] = field(default_factory=list)
    monetary_values: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)


@dataclass
class NumericChange:
    """A numeric value (percentage or amount) that changed between two versions."""

    old_value: str   # e.g. "20%"
    new_value: str   # e.g. "15%"
    context: str     # surrounding text from the new version


# ── Public API ────────────────────────────────────────────────────────────────

def extract_entities(text: str) -> ExtractedEntities:
    """Extract structured entities from regulatory text using regex patterns.

    Args:
        text: Plain text of a regulatory provision.

    Returns:
        ExtractedEntities populated with matches.
    """
    entities = ExtractedEntities(
        dates=[m.group(0) for m in _DATE_PATTERN.finditer(text)],
        articles=[m.group(0) for m in _ARTICLE_PATTERN.finditer(text)],
        percentages=[m.group(0) for m in _PERCENTAGE_PATTERN.finditer(text)],
        monetary_values=[m.group(0) for m in _MONETARY_PATTERN.finditer(text)],
        penalties=[m.group(0) for m in _PENALTY_PATTERN.finditer(text)],
    )
    logger.debug(
        "Entities: %d dates, %d articles, %d%%, %d monetary, %d penalties",
        len(entities.dates), len(entities.articles), len(entities.percentages),
        len(entities.monetary_values), len(entities.penalties),
    )
    return entities


def extract_numeric_changes(old_text: str, new_text: str) -> list[NumericChange]:
    """Detect numeric values (percentages) that changed between two section versions.

    Algorithm:
        Zip old and new percentage matches by position index — the N-th percentage
        in the old text corresponds to the N-th percentage in the new text.
        This is robust when the same paragraph is amended (e.g. "20% … 30%"
        becomes "15% … 25%") because the sentence structure stays the same.

    Args:
        old_text: Previous version of the section text.
        new_text: New version of the section text.

    Returns:
        List of NumericChange where old_value ≠ new_value, in appearance order.
    """
    if not old_text:
        return []

    old_matches = list(_PERCENTAGE_PATTERN.finditer(old_text))
    new_matches = list(_PERCENTAGE_PATTERN.finditer(new_text))

    changes: list[NumericChange] = []
    for old_m, new_m in zip(old_matches, new_matches):
        old_val, new_val = old_m.group(0), new_m.group(0)
        if old_val == new_val:
            continue
        start = max(0, new_m.start() - _CONTEXT_WINDOW)
        end = min(len(new_text), new_m.end() + _CONTEXT_WINDOW)
        context = new_text[start:end].strip()
        changes.append(NumericChange(old_value=old_val, new_value=new_val, context=context[:120]))

    logger.debug("Numeric changes found: %d", len(changes))
    return changes


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_with_context(text: str, pattern: re.Pattern) -> list[tuple[str, str]]:
    """Return (matched_value, surrounding_context) pairs for every pattern match."""
    results: list[tuple[str, str]] = []
    for m in pattern.finditer(text):
        start = max(0, m.start() - _CONTEXT_WINDOW)
        end = min(len(text), m.end() + _CONTEXT_WINDOW)
        ctx = text[start:end].strip()
        results.append((m.group(0), ctx))
    return results
