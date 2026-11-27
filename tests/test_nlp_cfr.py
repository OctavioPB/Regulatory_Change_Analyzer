"""NLP fixes found by the eCFR change-detection eval (real SEC amendments, 2026-11-27)."""
from src.models.document import ChangeType
from src.nlp.classifier import classify_modification
from src.nlp.comparator import compare_sections
from src.nlp.pipeline import analyze
from src.nlp.regulation_id import regulation_key, title_prefilter
from src.nlp.section_splitter import split_into_sections

T2 = """§ 240.15c6-1 Settlement cycle.
(a) Except as provided in paragraphs (b), (c), and (d) of this section, a broker or dealer shall not effect a contract that provides for payment of funds and delivery of securities later than the third business day after the date of the contract.
(b)(1) Paragraph (a) of this section shall not apply to contracts for limited partnership interests;
(i) Roman numeral under (b)(1), not the letter i.
(c) Firm commitment offerings priced after 4:30 p.m.
"""


def test_cfr_text_splits_on_lettered_paragraphs_in_sequence():
    sections = split_into_sections(T2)
    assert list(sections) == ["__preamble__", "(a)", "(b)", "(c)"]  # "(i)" stays inside (b)
    assert sections["(b)"].startswith("(b)(1) Paragraph (a)")
    assert "Roman numeral" in sections["(b)"]


def test_circulars_keep_their_article_split():
    circ = "CNBV\nArtículo 1. Las SOFOM (a) deberán... (b) y...\nArtículo 2. Plazo de 90 días."
    assert list(split_into_sections(circ)) == ["artículo 1", "artículo 2"]


def test_one_word_change_in_a_long_paragraph_is_detected():
    """T+3 → T+2: 'third' → 'second' was under the old 0.02 character-ratio threshold."""
    diffs = compare_sections(T2, T2.replace("third business day", "second business day"))
    assert [d.section_ref for d in diffs] == ["(a)"]


def test_spacing_and_punctuation_alone_are_not_changes():
    assert compare_sections(T2, T2.replace("contract.", "contract .").replace("  ", " ")) == []


def test_modifications_are_classified_by_what_changed():
    old = "Any person shall, within 10 days after the acquisition, file a statement. Such person must comply."
    assert classify_modification(old, old.replace("within 10 days", "within five business days")) is ChangeType.deadline
    limit = "El límite de contraparte se reduce del veinte por ciento (20%) del capital neto. Deberán cumplir."
    assert classify_modification(limit, limit.replace("20%", "15%")) is ChangeType.limit_modification
    # a large rewrite falls back to the whole-text rules
    assert classify_modification("short", "A new requirement: " + "word " * 60) is ChangeType.new_requirement


def test_pipeline_reports_only_the_changed_paragraph_with_its_type():
    result = analyze(T2.replace("third business day", "second business day"), T2)
    assert [(c.section_ref, c.change_type) for c in result.changes] == [("(a)", ChangeType.deadline)]


def test_cfr_citations_identify_the_regulation():
    assert regulation_key("17 CFR 240.15c6-1 — § 240.15c6-1 Settlement cycle.") == "cfr:17:240.15c6-1"
    assert regulation_key("17 C.F.R. § 275.206(4)-1 Investment adviser marketing") == "cfr:17:275.206(4)-1"
    assert regulation_key("17 CFR 240.17Ad-22") == "cfr:17:240.17ad-22"
    assert regulation_key("17 CFR 240.15c6-1") != regulation_key("17 CFR 240.15c6-2")
    assert title_prefilter("cfr:17:240.17ad-22") == "%240.17ad-22%"
    assert regulation_key("Circular 12/2025 que remite al 17 CFR 240.15c6-1") == "circular:12/2025"  # first wins
