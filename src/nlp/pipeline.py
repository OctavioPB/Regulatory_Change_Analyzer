import logging
from dataclasses import dataclass, field

from src.models.document import ChangeType
from src.nlp.classifier import classify_change
from src.nlp.comparator import SectionDiff, compare_sections
from src.nlp.extractor import ExtractedEntities, NumericChange, extract_entities, extract_numeric_changes

logger = logging.getLogger(__name__)

# Sections shorter than this (chars) are likely noise (page numbers, headers)
_MIN_SECTION_LENGTH = 20  # filter page numbers / empty headers, but keep short provisions


@dataclass
class SectionChange:
    """A single section that changed between two versions of a regulatory document."""

    section_ref: str
    change_type: ChangeType
    old_text: str | None
    new_text: str
    summary: str
    entities: ExtractedEntities
    numeric_changes: list[NumericChange] = field(default_factory=list)
    is_new: bool = False
    is_deleted: bool = False
    is_modified: bool = False


@dataclass
class AnalysisResult:
    """Full output of the NLP pipeline for one document."""

    total_sections_new: int
    total_sections_old: int
    changes: list[SectionChange]

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    @property
    def summary_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for ch in self.changes:
            counts[ch.change_type.value] = counts.get(ch.change_type.value, 0) + 1
        return counts


def analyze(new_text: str, old_text: str = "") -> AnalysisResult:
    """Run the full NLP pipeline on a regulatory document.

    Steps:
        1. Compare sections between old and new versions.
        2. For each changed section: extract entities, detect numeric changes,
           classify the change type.
        3. Return a structured AnalysisResult.

    When old_text is empty (first time the document is seen), every section
    in the new document is treated as a new section.

    Args:
        new_text: Current version of the regulatory text.
        old_text: Previous version (empty string if unavailable).

    Returns:
        AnalysisResult with one SectionChange per detected change.
    """
    section_diffs: list[SectionDiff] = compare_sections(old_text, new_text)

    from src.nlp.section_splitter import split_into_sections
    n_new = len(split_into_sections(new_text))
    n_old = len(split_into_sections(old_text)) if old_text.strip() else 0

    changes: list[SectionChange] = []
    for diff in section_diffs:
        change = _process_section_diff(diff)
        if change is not None:
            changes.append(change)

    logger.info(
        "Pipeline: %d section diffs → %d significant changes (new=%d mod=%d del=%d)",
        len(section_diffs),
        len(changes),
        sum(1 for c in changes if c.is_new),
        sum(1 for c in changes if c.is_modified),
        sum(1 for c in changes if c.is_deleted),
    )
    return AnalysisResult(
        total_sections_new=n_new,
        total_sections_old=n_old,
        changes=changes,
    )


def _process_section_diff(diff: SectionDiff) -> SectionChange | None:
    """Convert a SectionDiff into a SectionChange, or None if the section is noise."""
    active_text = diff.new_text or diff.old_text or ""

    if len(active_text) < _MIN_SECTION_LENGTH:
        logger.debug("Skipping short section '%s' (%d chars)", diff.section_ref, len(active_text))
        return None

    # For deleted sections, infer repeal from the fact that the section is gone
    if diff.is_deleted:
        change_type = ChangeType.repeal
    else:
        change_type = _classify_with_context(diff)

    entities = extract_entities(active_text)

    numeric_changes: list[NumericChange] = []
    if diff.is_modified and diff.old_text and diff.new_text:
        numeric_changes = extract_numeric_changes(diff.old_text, diff.new_text)

    summary = _build_summary(diff, change_type, numeric_changes)

    return SectionChange(
        section_ref=diff.section_ref,
        change_type=change_type,
        old_text=diff.old_text,
        new_text=active_text,
        summary=summary,
        entities=entities,
        numeric_changes=numeric_changes,
        is_new=diff.is_new,
        is_deleted=diff.is_deleted,
        is_modified=diff.is_modified,
    )


def _classify_with_context(diff: SectionDiff) -> ChangeType:
    """Classify a section change using both new and old text for context."""
    # Use old_text hint: if old had content and new has nothing, it's a repeal
    if diff.is_deleted:
        return ChangeType.repeal

    text = (diff.new_text or "") + "\n" + (diff.old_text or "")
    return classify_change(text)


def _build_summary(
    diff: SectionDiff,
    change_type: ChangeType,
    numeric_changes: list[NumericChange],
) -> str:
    """Produce a one-line human-readable summary of the change."""
    ref = diff.section_ref.title()

    if diff.is_deleted:
        return f"{ref}: section removed (possible repeal)"

    if diff.is_new:
        return f"{ref}: new section added ({change_type.value})"

    if numeric_changes:
        changes_str = "; ".join(
            f"{nc.old_value} → {nc.new_value}" for nc in numeric_changes[:3]
        )
        return f"{ref}: numeric values changed — {changes_str}"

    return f"{ref}: content modified ({change_type.value}, ratio={diff.change_ratio:.2f})"
