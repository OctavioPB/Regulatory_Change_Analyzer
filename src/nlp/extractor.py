import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Patterns for common regulatory entity types
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
_PENALTY_PATTERN = re.compile(
    r"\b(multa|penalidad|sanci[óo]n|fine|penalty|sanction)\b.{0,100}",
    re.IGNORECASE,
)


@dataclass
class ExtractedEntities:
    """Named entities and key values found in a regulatory text."""

    dates: list[str] = field(default_factory=list)
    articles: list[str] = field(default_factory=list)
    percentages: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)


def extract_entities(text: str) -> ExtractedEntities:
    """Extract structured entities from regulatory text using regex patterns.

    Args:
        text: Plain text of a regulatory provision.

    Returns:
        ExtractedEntities populated with matches found.
    """
    entities = ExtractedEntities(
        dates=[m.group(0) for m in _DATE_PATTERN.finditer(text)],
        articles=[m.group(0) for m in _ARTICLE_PATTERN.finditer(text)],
        percentages=[m.group(0) for m in _PERCENTAGE_PATTERN.finditer(text)],
        penalties=[m.group(0) for m in _PENALTY_PATTERN.finditer(text)],
    )
    logger.debug(
        "Entities: %d dates, %d articles, %d %%, %d penalties",
        len(entities.dates),
        len(entities.articles),
        len(entities.percentages),
        len(entities.penalties),
    )
    return entities
