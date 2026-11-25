"""The eval graders — a wrong grader silently corrupts every model comparison."""
from evals.cases import QACase
from evals.run import grade_answer, grade_draft, has_any, norm, pick_alerts

CITES = [{"type": "regulation", "ref_id": 1}, {"type": "contract", "ref_id": 2}]


def test_norm_folds_accents_case_and_digit_separators():
    assert norm("MXN 100,000 — Artículo") == "mxn 100000 — articulo"
    assert has_any("umbral de 100 000 pesos", ["100000"])


def test_answerable_needs_facts_and_valid_citations():
    case = QACase("c", "q", facts=[["15%", "quince por ciento"]])
    ok = grade_answer(case, case.facts, "Se reduce al 15% [REG-1].", CITES, None)
    assert ok["passed"]
    assert not grade_answer(case, case.facts, "Se reduce al 15%.", CITES, None)["passed"]  # uncited
    bad = grade_answer(case, case.facts, "Se reduce al 15% [REG-9].", CITES, None)
    assert not bad["passed"] and bad["invalid_citations"] == ["REG-9"]
    refused = grade_answer(case, case.facts, "The documents don't contain sufficient information.", CITES, None)
    assert refused["false_refusal"] and not refused["passed"]


def test_unanswerable_passes_only_on_refusal():
    case = QACase("u", "q", answerable=False)
    assert grade_answer(case, [], "Los documentos no contienen información suficiente.", [], None)["passed"]
    assert not grade_answer(case, [], "El límite es 30%.", [], None)["passed"]
    assert not grade_answer(case, [], "no contienen", [], "timeout")["passed"]


def _truth():
    alert = {"title": "Circular 12/2025 — X: Artículo 5", "raw_text": "se reduce del 20% al 15%",
             "contracts": {"Loan Agreement": []}}
    return alert, {"clauses": {"Loan Agreement": ["Clause 3.1: leverage at 20%"]}, "alerts": [alert]}


def test_draft_grader_flags_invented_percentages_and_real_clauses():
    alert, truth = _truth()
    body = ("ADDENDUM TO LOAN AGREEMENT\nWHEREAS Circular 12/2025 lowers the limit to 15%;\n"
            "NOW THEREFORE\nARTICLE 1 — AMENDMENT TO CLAUSE 3.1\nGENERAL PROVISIONS ... full force and effect\n"
            "IN WITNESS WHEREOF [PARTY A] [DATE]\n" + "x" * 400)
    g = grade_draft(body, "Loan Agreement", alert, truth)
    assert g["passed"] and g["references_real_clause"] and g["structure"] == 1.0
    g2 = grade_draft(body.replace("15%", "12.5%"), "Loan Agreement", alert, truth)
    assert g2["unsupported_percentages"] == ["12.5"] and not g2["passed"]
    assert not grade_draft(body.replace("12/2025", "the circular"), "Loan Agreement", alert, truth)["passed"]
    g3 = grade_draft(body.replace("15%", "15.0%"), "Loan Agreement", alert, truth)  # same figure
    assert g3["unsupported_percentages"] == [] and g3["passed"]


def test_pick_alerts_takes_one_alert_per_document():
    truth = {"alerts": [
        {"title": "Circ A: Art 1", "contracts": {}},
        {"title": "Circ A: Art 2", "contracts": {"X": []}},
        {"title": "Circ A: Art 3", "contracts": {"Y": []}},
        {"title": "Circ B: Art 1", "contracts": {"Z": []}},
    ]}
    assert [a["title"] for a in pick_alerts(truth)] == ["Circ A: Art 2", "Circ B: Art 1"]
