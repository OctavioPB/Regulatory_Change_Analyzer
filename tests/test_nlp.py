import pytest

from src.nlp.classifier import classify_change
from src.nlp.comparator import TextDiff, compare_texts
from src.nlp.extractor import extract_entities
from src.models.document import ChangeType


def test_compare_texts_identical_returns_zero_ratio():
    text = "Article 5. The limit is 20%."
    diff = compare_texts(text, text)
    assert diff.change_ratio == 0.0
    assert diff.added_lines == []
    assert diff.removed_lines == []


def test_compare_texts_detects_changes():
    old = "The limit is 20%."
    new = "The limit is 15%."
    diff = compare_texts(old, new)
    assert diff.change_ratio > 0.0
    assert any("15%" in line for line in diff.added_lines)
    assert any("20%" in line for line in diff.removed_lines)


def test_compare_texts_unified_diff_non_empty_when_changed():
    diff = compare_texts("old text here", "new text here")
    assert len(diff.unified_diff) > 0


def test_classify_change_limit_modification():
    text = "El límite de contraparte se reduce de 20% a 15%."
    result = classify_change(text)
    assert result == ChangeType.limit_modification


def test_classify_change_new_requirement():
    text = "Los intermediarios deben ahora reportar mensualmente."
    result = classify_change(text)
    assert result == ChangeType.new_requirement


def test_classify_change_repeal():
    text = "Se deroga el Artículo 7 de la Circular 5/2020."
    result = classify_change(text)
    assert result == ChangeType.repeal


def test_classify_change_defaults_to_other():
    result = classify_change("Este artículo describe el contexto general del sector.")
    assert result == ChangeType.other


def test_extract_entities_finds_percentage():
    entities = extract_entities("El porcentaje máximo es 15%.")
    assert "15%" in entities.percentages


def test_extract_entities_finds_article():
    entities = extract_entities("Según el Artículo 5, párrafo 2, se establece...")
    assert len(entities.articles) >= 1


def test_extract_entities_empty_text_returns_empty():
    entities = extract_entities("")
    assert entities.dates == []
    assert entities.percentages == []
