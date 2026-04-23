"""Tests for the keyword rules engine."""

import pytest

from src.mapping.rules_engine import (
    RuleMatch,
    apply_rules,
    contracts_targeted_by_rules,
)
from src.models.impact import Severity


# ── apply_rules ───────────────────────────────────────────────────────────────

def test_apply_rules_returns_empty_for_irrelevant_text():
    text = "Este es un texto sin keywords regulatorios relevantes."
    matches = apply_rules(text)
    assert matches == []


def test_apply_rules_returns_empty_for_empty_string():
    assert apply_rules("") == []


def test_apply_rules_fires_sofom_rule():
    text = "La nueva circular establece límites para las SOFOM en México."
    matches = apply_rules(text)
    rule_ids = [m.rule_id for m in matches]
    assert "R001" in rule_ids


def test_apply_rules_fires_derivative_rule():
    text = "Se modifican los requerimientos para contratos de swap y derivados."
    matches = apply_rules(text)
    rule_ids = [m.rule_id for m in matches]
    assert "R002" in rule_ids


def test_apply_rules_fires_aml_rule():
    text = "Las instituciones deben reforzar sus controles de PLD conforme a GAFI."
    matches = apply_rules(text)
    rule_ids = [m.rule_id for m in matches]
    assert "R003" in rule_ids


def test_apply_rules_fires_privacy_rule():
    text = "El tratamiento de datos personales requiere consentimiento explícito."
    matches = apply_rules(text)
    rule_ids = [m.rule_id for m in matches]
    assert "R004" in rule_ids


def test_apply_rules_fires_fintech_rule():
    text = "Las Instituciones de Tecnología Financiera (ITF) deben cumplir con el nuevo marco."
    matches = apply_rules(text)
    rule_ids = [m.rule_id for m in matches]
    assert "R005" in rule_ids


def test_apply_rules_fires_capital_rule():
    text = "El coeficiente de apalancamiento mínimo se incrementa conforme a Basilea III."
    matches = apply_rules(text)
    rule_ids = [m.rule_id for m in matches]
    assert "R007" in rule_ids


def test_apply_rules_multiple_rules_can_fire():
    text = (
        "Las SOFOM que operen con derivados deberán reportar mensualmente "
        "y cumplir con los límites de capital establecidos."
    )
    matches = apply_rules(text)
    # R001 (SOFOM), R002 (derivados), R006 (reporte), R007 (capital) should fire
    rule_ids = {m.rule_id for m in matches}
    assert "R001" in rule_ids
    assert "R002" in rule_ids


def test_apply_rules_match_has_correct_fields():
    text = "Se modifica el límite de crédito para instituciones financieras."
    matches = apply_rules(text)
    assert len(matches) >= 1
    m = matches[0]
    assert isinstance(m, RuleMatch)
    assert m.rule_id
    assert isinstance(m.contract_types, list)
    assert isinstance(m.areas, list)
    assert isinstance(m.severity, Severity)
    assert m.matched_keyword


def test_apply_rules_severity_is_valid_enum():
    text = "Los fondos de inversión deben ajustar sus portafolios."
    matches = apply_rules(text)
    rule_ids = [m.rule_id for m in matches]
    assert "R008" in rule_ids
    inv_match = next(m for m in matches if m.rule_id == "R008")
    assert inv_match.severity == Severity.medium


def test_apply_rules_case_insensitive():
    text = "New regulations for LOAN products require immediate action."
    matches = apply_rules(text)
    rule_ids = [m.rule_id for m in matches]
    assert "R001" in rule_ids


# ── contracts_targeted_by_rules ───────────────────────────────────────────────

def test_contracts_targeted_aggregates_types_and_areas():
    text = (
        "Las SOFOM con contratos de swap deben cumplir con los controles de AML."
    )
    matches = apply_rules(text)
    types, areas = contracts_targeted_by_rules(matches)
    # R001 adds "loan", "credit", "mortgage" / R002 adds "derivative", "swap" / R003 adds "onboarding"
    assert "loan" in types
    assert "swap" in types or "derivative" in types
    assert "AML" in areas or "Compliance" in areas


def test_contracts_targeted_empty_on_no_matches():
    types, areas = contracts_targeted_by_rules([])
    assert types == set()
    assert areas == set()


def test_contracts_targeted_deduplicates():
    # Two rules that both target "loan"
    text = "La nueva circular sobre crédito y fintech afecta los préstamos."
    matches = apply_rules(text)
    types, areas = contracts_targeted_by_rules(matches)
    # Even if R001 and R005 both include "loan", the set should deduplicate
    assert isinstance(types, set)
    loan_count = list(types).count("loan")
    assert loan_count == 1
