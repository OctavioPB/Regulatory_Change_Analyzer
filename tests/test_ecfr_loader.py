"""eCFR / Federal Register loaders and the change-detection grader — offline, no network."""
import json
from types import SimpleNamespace

import httpx

from evals.change_detection import _missing_facts, grade_case, render
from evals.ecfr_cases import EcfrCase, Fact
from evals.sources.ecfr import EcfrClient, compare, parse_fr_date, parse_section_xml
from evals.sources.federal_register import FederalRegisterClient, amendatory_instruction

XML_BEFORE = """<?xml version="1.0" encoding="UTF-8"?>
<DIV8 N="240.15c6-1" TYPE="SECTION">
<HEAD>§ 240.15c6-1 Settlement cycle.</HEAD>
<XREF ID="20230306">Link to an amendment published at 88 FR 13952, Mar. 6, 2023.</XREF>
<P>(a) Payment later than the second business day after the date of the contract.</P>
<P>(b) Paragraph (a) shall not apply to contracts:</P>
<P>(1) For limited partnership interests;</P>
<P>(2) Exempted by order.</P>
<P>(c) Firm commitment offerings: the fourth business day.</P>
<CITA TYPE="N">[58 FR 52903, Oct. 13, 1993, as amended at 82 FR 15601, Mar. 29, 2017]</CITA>
</DIV8>"""

XML_AFTER = XML_BEFORE.replace("second business day", "first business day").replace(
    "<P>(2) Exempted by order.</P>", "<P>(2) Security-based swaps; or</P>\n<P>(3) Exempted by order.</P>").replace(
    "82 FR 15601, Mar. 29, 2017]", "82 FR 15601, Mar. 29, 2017; 88 FR 13952, Mar. 6, 2023]")


def test_section_xml_becomes_labelled_paragraphs():
    s = parse_section_xml(XML_BEFORE, citation="17 CFR 240.15c6-1", on="2023-05-04")
    assert s.heading == "§ 240.15c6-1 Settlement cycle."
    assert [p for p, _ in s.paragraphs] == ["(a)", "(b)", "(b)(1)", "(b)(2)", "(c)"]
    assert "Link to an amendment" not in s.render()  # XREF/CITA are metadata, not rule text


def test_labels_resolve_letters_vs_roman_numerals():
    xml = """<DIV8><HEAD>§ 1</HEAD><P>(h) H.</P><P>(i) Letter i after h.</P><P>(1) One.</P>
             <P>(i) Roman under (i)(1).</P><P>(ii) Roman two.</P><P>(A) Upper.</P><P>(j) Next letter.</P>
             <P>(c) (1)(i) Labels separated by spaces.</P></DIV8>"""
    paths = [p for p, _ in parse_section_xml(xml, citation="x", on="d").paragraphs]
    assert paths == ["(h)", "(i)", "(i)(1)", "(i)(1)(i)", "(i)(1)(ii)", "(i)(1)(ii)(A)", "(j)", "(c)(1)(i)"]


def test_compare_is_by_official_label_and_ignores_whitespace():
    b = parse_section_xml(XML_BEFORE, citation="x", on="b")
    a = parse_section_xml(XML_AFTER.replace("(c) Firm", "(c)   Firm"), citation="x", on="a")
    assert compare(b, a) == {"added": ["(b)(3)"], "removed": [], "modified": ["(a)", "(b)(2)"]}


def test_last_amendment_is_the_newest_reference():
    a = parse_section_xml(XML_AFTER, citation="x", on="a")
    assert a.last_amendment() == (88, 13952, "Mar. 6, 2023")
    assert parse_fr_date("Sept. 9, 2022") == "2022-09-09" and parse_fr_date("junk") is None


def test_ecfr_client_caches_and_requests_compression(tmp_path):
    calls = []

    def handler(req: httpx.Request):
        calls.append(req)
        return httpx.Response(200, text=XML_BEFORE)

    client = EcfrClient(cache_dir=tmp_path, transport=httpx.MockTransport(handler))
    client.section(17, "240.15c6-1", "2023-05-04")
    client.section(17, "240.15c6-1", "2023-05-04")
    assert len(calls) == 1  # second read comes from the cache
    req = calls[0]
    assert "gzip" in req.headers["accept-encoding"]
    assert "@" not in req.headers["user-agent"]  # no personal contact details
    assert req.url.params["section"] == "240.15c6-1" and req.url.params["part"] == "240"


FR_TEXT = """
PART 240--GENERAL RULES

0
5. Amend Sec.  240.13d-1 by:
0
    a. Revising paragraph (a); and
    b. Adding paragraph (k).

Sec.  240.13d-1  Filing of Schedules 13D and 13G.

10. Section 270.35d-1 is revised to read as follows:
"""


def test_amendatory_instruction_keeps_sub_steps_and_drops_markers():
    assert amendatory_instruction(FR_TEXT, "240.13d-1") == (
        "5. Amend Sec. 240.13d-1 by: a. Revising paragraph (a); and b. Adding paragraph (k).")
    assert amendatory_instruction(FR_TEXT, "270.35d-1") == "10. Section 270.35d-1 is revised to read as follows:"
    assert amendatory_instruction(FR_TEXT, "240.13d-2") is None


def test_find_rule_matches_page_then_falls_back_to_effective_date(tmp_path):
    rule = {"document_number": "2023-03566", "title": "T+1", "citation": "88 FR 13872", "start_page": 13872,
            "end_page": 13954, "publication_date": "2023-03-06", "effective_on": "2023-05-05",
            "type": "Rule", "html_url": "u", "abstract": ""}

    def handler(req: httpx.Request):
        by_pub = any("publication_date" in k for k in req.url.params.keys())
        return httpx.Response(200, json={"results": [rule] if by_pub else []})

    fr = FederalRegisterClient(cache_dir=tmp_path, transport=httpx.MockTransport(handler))
    assert fr.find_rule(agency="sec", published="2023-03-06", page=13952).citation == "88 FR 13872"
    # page outside every range, but only one rule that day → that rule
    assert fr.find_rule(agency="sec", published="2023-03-06", page=1).document_number == "2023-03566"


def _fixture():
    b = parse_section_xml(XML_BEFORE, citation="17 CFR 240.15c6-1", on="b")
    a = parse_section_xml(XML_AFTER, citation="17 CFR 240.15c6-1", on="a")
    return json.loads(json.dumps({
        "id": "t", "citation": a.citation, "heading": a.heading, "substantive": True,
        "before": {"paragraphs": b.paragraphs}, "after": {"paragraphs": a.paragraphs},
        "truth": compare(b, a), "change_types": ["deadline"],
        "facts": [{"old": "second business day", "new": "first business day"}],
    }))


def _change(old, new, ctype="deadline", ref="__document__"):
    return SimpleNamespace(old_text=old, new_text=new, change_type=SimpleNamespace(value=ctype),
                           section_ref=ref, numeric_changes=[])


def test_grader_needs_detection_facts_on_the_right_side_type_and_precision():
    fx = _fixture()  # truly changed units: (a) and (b)
    before, after = dict(fx["before"]["paragraphs"]), dict(fx["after"]["paragraphs"])
    a = _change(before["(a)"], after["(a)"], ref="(a)")
    b = _change(before["(b)(2)"], after["(b)(2)"], ref="(b)")
    g = grade_case(fx, SimpleNamespace(changes=[a, b]))
    assert g["passed"] and g["unit_recall"] == 1.0 and g["unit_precision"] == 1.0 and g["localized"]
    # flagging the whole document finds the change but buries it: precision 0 → fail
    whole = _change(render(fx["before"], fx["heading"]), render(fx["after"], fx["heading"]))
    g = grade_case(fx, SimpleNamespace(changes=[whole]))
    assert not g["passed"] and g["flagged_share"] == 1.0 and g["unit_precision"] == 0.0
    # one false unit out of three is tolerated, a majority of false units is not
    noise = [_change("x y", "x z", ref=r) for r in ("(c)", "(d)", "(e)")]
    assert grade_case(fx, SimpleNamespace(changes=[a, b, noise[0]]))["passed"]
    assert not grade_case(fx, SimpleNamespace(changes=[a, b, *noise]))["passed"]
    swapped = _change(a.new_text, a.old_text, ref="(a)")  # fact on the wrong side
    assert not grade_case(fx, SimpleNamespace(changes=[swapped, b]))["passed"]
    assert not grade_case(fx, SimpleNamespace(changes=[_change(a.old_text, a.new_text, "other", "(a)")]))["passed"]
    assert not grade_case(fx, SimpleNamespace(changes=[]))["passed"]


def test_article_refs_map_to_law_article_keys():
    from evals.change_detection import _unit_of_ref

    assert _unit_of_ref("artículo 107 bis", "article") == "107 bis"
    assert _unit_of_ref("artículo 8o", "article") == "8"
    assert _unit_of_ref("artículo 17-h", "article") == "17-h"
    assert _unit_of_ref("capítulo ii", "article") == "capítulo ii"
    assert _unit_of_ref("(b)", "paragraph") == "(b)"


def test_controls_pass_only_when_nothing_is_reported():
    fx = _fixture() | {"substantive": False, "facts": [], "change_types": []}
    assert grade_case(fx, SimpleNamespace(changes=[]))["passed"]
    assert not grade_case(fx, SimpleNamespace(changes=[_change("a", "b")]))["passed"]


def test_build_rejects_facts_missing_from_the_fetched_text():
    case = EcfrCase("x", "240.15c6-1", "2023-05-05", facts=(Fact("third business day", "first business day"),))
    assert _missing_facts(case, "the second business day", "the first business day") == ["old: third business day"]
