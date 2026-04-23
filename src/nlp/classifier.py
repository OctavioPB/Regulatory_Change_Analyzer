import logging
import re

from src.models.document import ChangeType

logger = logging.getLogger(__name__)

# Keyword sets for rule-based classification (Sprint 2 baseline)
_RULES: list[tuple[ChangeType, list[str]]] = [
    (ChangeType.repeal, ["deroga", "derogado", "repeal", "repealed", "abrogat"]),
    (ChangeType.new_requirement, ["nuevo", "nueva", "adiciona", "new requirement", "shall now", "must"]),
    (ChangeType.limit_modification, ["límite", "limite", "umbral", "threshold", "limit", "porcentaje", "percentage", "%"]),
    (ChangeType.deadline, ["plazo", "fecha límite", "deadline", "within", "no later than", "a más tardar"]),
    (ChangeType.clarification, ["aclara", "precisa", "clarif", "means", "defined as", "se entiende"]),
]


def classify_change(text: str) -> ChangeType:
    """Rule-based classification of a regulatory change text.

    Uses keyword matching as a Sprint 2 baseline; replace with a fine-tuned
    Legal-BERT classifier once training data is available.

    Args:
        text: Plain text of the changed provision.

    Returns:
        The most likely ChangeType, defaulting to ChangeType.other.
    """
    text_lower = text.lower()
    for change_type, keywords in _RULES:
        if any(kw in text_lower for kw in keywords):
            logger.debug("Classified as %s (keyword match)", change_type.value)
            return change_type

    logger.debug("Classification defaulted to 'other'")
    return ChangeType.other
