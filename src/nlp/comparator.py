import difflib
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextDiff:
    """Result of comparing two versions of a regulatory text."""

    added_lines: list[str]
    removed_lines: list[str]
    unified_diff: str
    change_ratio: float  # 0.0 (identical) → 1.0 (completely different)


def compare_texts(old_text: str, new_text: str) -> TextDiff:
    """Compare two versions of a regulatory document line by line.

    Args:
        old_text: Previous version of the text.
        new_text: New version of the text.

    Returns:
        TextDiff with added/removed lines and a similarity ratio.
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    added: list[str] = []
    removed: list[str] = []

    differ = difflib.Differ()
    diff = list(differ.compare(old_lines, new_lines))

    for line in diff:
        if line.startswith("+ "):
            added.append(line[2:].rstrip())
        elif line.startswith("- "):
            removed.append(line[2:].rstrip())

    unified = "".join(
        difflib.unified_diff(old_lines, new_lines, fromfile="previous", tofile="current", lineterm="")
    )

    matcher = difflib.SequenceMatcher(None, old_text, new_text)
    change_ratio = 1.0 - matcher.ratio()

    logger.debug(
        "Text diff: +%d lines, -%d lines, change_ratio=%.3f",
        len(added),
        len(removed),
        change_ratio,
    )
    return TextDiff(
        added_lines=added,
        removed_lines=removed,
        unified_diff=unified,
        change_ratio=change_ratio,
    )


def extract_changed_sections(diff: TextDiff, context_lines: int = 2) -> list[str]:
    """Group contiguous added lines into change sections for downstream NLP.

    Args:
        diff: Result of compare_texts.
        context_lines: Not used yet; reserved for future context-aware grouping.

    Returns:
        List of text blocks representing each discrete change.
    """
    if not diff.added_lines:
        return []
    return ["\n".join(diff.added_lines)]
