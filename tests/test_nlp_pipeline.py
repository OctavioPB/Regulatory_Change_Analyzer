"""Tests for the NLP pipeline — section splitter, comparator, extractor, pipeline."""

import pytest

from src.models.document import ChangeType
from src.nlp.comparator import SectionDiff, compare_sections
from src.nlp.extractor import extract_entities, extract_numeric_changes
from src.nlp.pipeline import AnalysisResult, SectionChange, analyze
from src.nlp.section_splitter import split_into_sections


# ── section_splitter ──────────────────────────────────────────────────────────

def test_split_recognises_spanish_articles():
    text = (
        "Artículo 5. El límite de contraparte es del 20%.\n\n"
        "Artículo 6. Los plazos de reporte serán mensuales.\n\n"
        "Artículo 7. Se deroga la disposición anterior."
    )
    sections = split_into_sections(text)
    assert len(sections) == 3
    keys = list(sections.keys())
    assert any("artículo 5" in k for k in keys)
    assert any("artículo 6" in k for k in keys)


def test_split_recognises_english_sections():
    text = (
        "Section 1. General provisions.\n\n"
        "Section 2. Reporting requirements.\n\n"
        "Section 3. Penalties for non-compliance."
    )
    sections = split_into_sections(text)
    assert len(sections) == 3


def test_split_fallback_for_unsectioned_text():
    text = "This document has no section headers. It contains general information."
    sections = split_into_sections(text)
    assert "__document__" in sections
    assert len(sections) == 1


def test_split_headers_are_normalised_lowercase():
    text = "ARTÍCULO 5. Texto del artículo."
    sections = split_into_sections(text)
    keys = list(sections.keys())
    assert all(k == k.lower() for k in keys)


def test_split_body_contains_article_text():
    text = "Artículo 5. El límite es del 20 por ciento.\n\nArtículo 6. Otro artículo."
    sections = split_into_sections(text)
    body = next(v for k, v in sections.items() if "5" in k)
    assert "20 por ciento" in body


def test_split_chapter_and_article_mixed():
    text = (
        "Capítulo I. Disposiciones Generales.\n\n"
        "Artículo 1. Objeto de la presente circular.\n\n"
        "Artículo 2. Definiciones aplicables."
    )
    sections = split_into_sections(text)
    assert len(sections) == 3


# ── compare_sections ──────────────────────────────────────────────────────────

def _doc_v1() -> str:
    return (
        "Artículo 5. El límite de contraparte es del 20%.\n\n"
        "Artículo 6. Los plazos serán de 30 días hábiles."
    )


def _doc_v2() -> str:
    return (
        "Artículo 5. El límite de contraparte es del 15%.\n\n"
        "Artículo 6. Los plazos serán de 30 días hábiles.\n\n"
        "Artículo 7. Nueva obligación de reporte trimestral."
    )


def test_compare_sections_detects_modified_section():
    diffs = compare_sections(_doc_v1(), _doc_v2())
    modified = [d for d in diffs if d.is_modified]
    assert len(modified) >= 1
    assert any("5" in d.section_ref for d in modified)


def test_compare_sections_detects_new_section():
    diffs = compare_sections(_doc_v1(), _doc_v2())
    new = [d for d in diffs if d.is_new]
    assert len(new) >= 1
    assert any("7" in d.section_ref for d in new)


def test_compare_sections_unchanged_section_not_in_diffs():
    diffs = compare_sections(_doc_v1(), _doc_v2())
    refs = [d.section_ref for d in diffs]
    # Article 6 is identical — must not appear in diffs
    assert not any("artículo 6" == ref for ref in refs)


def test_compare_sections_deleted_section():
    old = _doc_v2()
    new = _doc_v1()  # swap: v1 doesn't have Article 7
    diffs = compare_sections(old, new)
    deleted = [d for d in diffs if d.is_deleted]
    assert any("7" in d.section_ref for d in deleted)


def test_compare_sections_empty_old_makes_everything_new():
    diffs = compare_sections("", _doc_v1())
    assert all(d.is_new for d in diffs)
    assert len(diffs) == 2


# ── extract_numeric_changes ───────────────────────────────────────────────────

def test_extract_numeric_changes_finds_percentage_change():
    old = "El límite de contraparte no excederá el 20% del capital total."
    new = "El límite de contraparte no excederá el 15% del capital total."
    changes = extract_numeric_changes(old, new)
    assert len(changes) == 1
    assert changes[0].old_value == "20%"
    assert changes[0].new_value == "15%"


def test_extract_numeric_changes_no_change_when_values_same():
    text = "El límite es del 20%."
    changes = extract_numeric_changes(text, text)
    assert changes == []


def test_extract_numeric_changes_empty_old_returns_empty():
    new = "El límite es del 15%."
    changes = extract_numeric_changes("", new)
    assert changes == []


def test_extract_numeric_changes_multiple_different_limits():
    old = "El límite de contraparte es 20% y el de concentración es 30%."
    new = "El límite de contraparte es 15% y el de concentración es 25%."
    changes = extract_numeric_changes(old, new)
    assert len(changes) == 2
    old_vals = {c.old_value for c in changes}
    assert "20%" in old_vals
    assert "30%" in old_vals


# ── full pipeline ─────────────────────────────────────────────────────────────

def test_analyze_detects_limit_modification():
    result = analyze(_doc_v2(), _doc_v1())
    limit_changes = [c for c in result.changes if c.change_type == ChangeType.limit_modification]
    assert len(limit_changes) >= 1


def test_analyze_detects_new_section_as_new_requirement_or_other():
    result = analyze(_doc_v2(), _doc_v1())
    new_sections = [c for c in result.changes if c.is_new]
    assert len(new_sections) >= 1


def test_analyze_new_section_has_numeric_changes():
    result = analyze(_doc_v2(), _doc_v1())
    modified = [c for c in result.changes if c.is_modified]
    changes_with_numerics = [c for c in modified if c.numeric_changes]
    assert len(changes_with_numerics) >= 1
    nc = changes_with_numerics[0].numeric_changes[0]
    assert nc.old_value == "20%"
    assert nc.new_value == "15%"


def test_analyze_no_old_text_returns_all_new():
    result = analyze(_doc_v1(), "")
    assert all(c.is_new for c in result.changes)


def test_analyze_result_has_changes_property():
    result = analyze(_doc_v2(), _doc_v1())
    assert result.has_changes is True


def test_analyze_identical_texts_returns_no_changes():
    result = analyze(_doc_v1(), _doc_v1())
    assert result.has_changes is False


def test_analyze_summary_counts_keys():
    result = analyze(_doc_v2(), _doc_v1())
    counts = result.summary_counts
    assert isinstance(counts, dict)
    assert all(isinstance(v, int) for v in counts.values())


def test_analyze_repeal_classified_for_deleted_section():
    old = (
        "Artículo 5. El límite es del 20%.\n\n"
        "Artículo 6. Esta disposición queda sin efecto."
    )
    new = "Artículo 5. El límite es del 20%."
    result = analyze(new, old)
    deleted = [c for c in result.changes if c.is_deleted]
    assert len(deleted) == 1
    assert deleted[0].change_type == ChangeType.repeal


def test_analyze_entities_populated():
    result = analyze(_doc_v2(), _doc_v1())
    for change in result.changes:
        assert isinstance(change.entities.percentages, list)
