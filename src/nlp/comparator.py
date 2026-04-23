import difflib
import logging
from dataclasses import dataclass

from src.nlp.section_splitter import split_into_sections

logger = logging.getLogger(__name__)

_SIMILARITY_THRESHOLD = 0.02  # detect even single-word changes (e.g. 20% → 15%)


@dataclass
class TextDiff:
    """Result of a whole-document line-level comparison."""

    added_lines: list[str]
    removed_lines: list[str]
    unified_diff: str
    change_ratio: float  # 0.0 identical → 1.0 completely different


@dataclass
class SectionDiff:
    """Result of comparing a single section between two document versions."""

    section_ref: str
    old_text: str | None   # None when the section is brand new
    new_text: str | None   # None when the section was deleted
    change_ratio: float    # 0.0 identical → 1.0 completely different
    is_new: bool
    is_deleted: bool
    is_modified: bool      # present in both but text differs


def compare_texts(old_text: str, new_text: str) -> TextDiff:
    """Compare two versions of a regulatory document line by line.

    Args:
        old_text: Previous version of the text (may be empty string).
        new_text: New version of the text.

    Returns:
        TextDiff with added/removed lines and a similarity ratio.
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    added: list[str] = []
    removed: list[str] = []

    for line in difflib.Differ().compare(old_lines, new_lines):
        if line.startswith("+ "):
            added.append(line[2:].rstrip())
        elif line.startswith("- "):
            removed.append(line[2:].rstrip())

    unified = "".join(
        difflib.unified_diff(old_lines, new_lines, fromfile="previous", tofile="current", lineterm="")
    )
    change_ratio = 1.0 - difflib.SequenceMatcher(None, old_text, new_text).ratio()

    logger.debug("Text diff: +%d -%d lines, ratio=%.3f", len(added), len(removed), change_ratio)
    return TextDiff(added_lines=added, removed_lines=removed, unified_diff=unified, change_ratio=change_ratio)


def compare_sections(old_text: str, new_text: str) -> list[SectionDiff]:
    """Section-level comparison between two versions of a regulatory document.

    Each document is split into sections (by article/section header). Sections
    are then matched by header key; unmatched sections in new → is_new; in old
    only → is_deleted; in both with differing text → is_modified.

    Args:
        old_text: Previous version (may be empty → all sections classified as new).
        new_text: Current version of the regulatory text.

    Returns:
        List of SectionDiff, one per detected change. Identical sections are omitted.
    """
    old_sections = split_into_sections(old_text) if old_text.strip() else {}
    new_sections = split_into_sections(new_text)

    diffs: list[SectionDiff] = []

    # Sections that exist in the new version
    for key, new_body in new_sections.items():
        if key not in old_sections:
            diffs.append(SectionDiff(
                section_ref=key,
                old_text=None,
                new_text=new_body,
                change_ratio=1.0,
                is_new=True,
                is_deleted=False,
                is_modified=False,
            ))
        else:
            old_body = old_sections[key]
            ratio = 1.0 - difflib.SequenceMatcher(None, old_body, new_body).ratio()
            if ratio > _SIMILARITY_THRESHOLD:
                diffs.append(SectionDiff(
                    section_ref=key,
                    old_text=old_body,
                    new_text=new_body,
                    change_ratio=ratio,
                    is_new=False,
                    is_deleted=False,
                    is_modified=True,
                ))

    # Sections that existed in the old version but not the new
    for key, old_body in old_sections.items():
        if key not in new_sections:
            diffs.append(SectionDiff(
                section_ref=key,
                old_text=old_body,
                new_text=None,
                change_ratio=1.0,
                is_new=False,
                is_deleted=True,
                is_modified=False,
            ))

    logger.debug("Section comparison: %d diffs (new=%d modified=%d deleted=%d)",
                 len(diffs),
                 sum(1 for d in diffs if d.is_new),
                 sum(1 for d in diffs if d.is_modified),
                 sum(1 for d in diffs if d.is_deleted))
    return diffs


def extract_changed_sections(diff: TextDiff, context_lines: int = 2) -> list[str]:
    """Group contiguous added lines into change blocks (whole-document fallback).

    Args:
        diff: Result of compare_texts.
        context_lines: Reserved for future context-aware grouping.

    Returns:
        List of text blocks, one per contiguous added region.
    """
    if not diff.added_lines:
        return []
    return ["\n".join(diff.added_lines)]
