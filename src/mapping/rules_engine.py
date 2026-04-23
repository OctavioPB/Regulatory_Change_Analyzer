import logging
import re
from dataclasses import dataclass

from src.models.impact import Severity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

# Each rule: triggers when ANY keyword in `keywords` appears in the text.
# `contract_types` and `areas` identify which contracts/processes to flag.
_RULES: list[dict] = [
    {
        "id": "R001",
        "keywords": [
            r"\bSOFOM\b", r"\bcrédito\b", r"\bpréstamo\b", r"\bhipoteca\b",
            r"\bloan\b", r"\bcredit\b", r"\bmortgage\b",
        ],
        "contract_types": ["loan", "credit", "mortgage"],
        "areas": ["Risk", "Legal"],
        "severity": "high",
        "description": "SOFOM/credit regulation — affects loan and credit contracts",
    },
    {
        "id": "R002",
        "keywords": [
            r"\bderivado\b", r"\bderivados\b", r"\bswap\b", r"\bfuturo\b",
            r"\bopc[ií]on\b", r"\bderivative\b", r"\bforward\b",
        ],
        "contract_types": ["derivative", "swap"],
        "areas": ["Risk", "Treasury"],
        "severity": "high",
        "description": "Derivatives regulation — affects derivative and swap contracts",
    },
    {
        "id": "R003",
        "keywords": [
            r"\blandc?\b", r"\blavado\b", r"\bPLD\b", r"\banti-money\b",
            r"\bAML\b", r"\bFATF\b", r"\bGAFI\b",
        ],
        "contract_types": ["onboarding", "service"],
        "areas": ["AML", "Compliance"],
        "severity": "high",
        "description": "AML/PLD regulation — affects onboarding and compliance processes",
    },
    {
        "id": "R004",
        "keywords": [
            r"\bdatos personales\b", r"\bprivacidad\b", r"\bprotección de datos\b",
            r"\bpersonal data\b", r"\bprivacy\b", r"\bGDPR\b", r"\bLFPDP\b",
        ],
        "contract_types": ["service", "data_processing"],
        "areas": ["Legal", "Compliance", "IT"],
        "severity": "medium",
        "description": "Data privacy regulation — affects service and data processing contracts",
    },
    {
        "id": "R005",
        "keywords": [
            r"\bfintech\b", r"\bITF\b", r"\bInstitución de Tecnolog[ií]a Financiera\b",
            r"\bcrowdfunding\b", r"\bpago electrónico\b",
        ],
        "contract_types": ["loan", "service", "payment"],
        "areas": ["Legal", "Risk", "Compliance"],
        "severity": "high",
        "description": "Fintech regulation — affects loan, service, and payment contracts",
    },
    {
        "id": "R006",
        "keywords": [
            r"\breporte regulatorio\b", r"\binforme\b", r"\breporting\b",
            r"\bdivulgación\b", r"\bdisclosure\b", r"\bSAR\b",
        ],
        "contract_types": ["service"],
        "areas": ["Compliance", "Risk"],
        "severity": "medium",
        "description": "Reporting obligation — affects compliance and risk processes",
    },
    {
        "id": "R007",
        "keywords": [
            r"\bcapital\b", r"\bapalancamiento\b", r"\bleverage\b",
            r"\bBasilea\b", r"\bBasel\b", r"\bcoeficiente\b",
        ],
        "contract_types": ["loan", "derivative", "credit"],
        "areas": ["Risk", "Treasury"],
        "severity": "high",
        "description": "Capital/leverage requirement — affects loan and derivative contracts",
    },
    {
        "id": "R008",
        "keywords": [
            r"\bfondos? de inversión\b", r"\bfondos? mutuos?\b", r"\bmutual funds?\b",
            r"\binvestment funds?\b", r"\bfideicomiso\b", r"\btrust\b",
        ],
        "contract_types": ["investment", "fiduciary"],
        "areas": ["Legal", "Compliance"],
        "severity": "medium",
        "description": "Investment fund/trust regulation — affects investment and fiduciary contracts",
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class RuleMatch:
    """A rules-engine match for a single rule firing on regulatory text."""

    rule_id: str
    contract_types: list[str]
    areas: list[str]
    severity: Severity
    description: str
    matched_keyword: str


def apply_rules(text: str) -> list[RuleMatch]:
    """Apply all keyword rules against a piece of regulatory text.

    Each rule fires if ANY of its keywords appears in the text (case-insensitive).

    Args:
        text: Regulatory change text to evaluate.

    Returns:
        List of RuleMatch, one per fired rule, in definition order.
        Empty list if no rules match.
    """
    if not text:
        return []

    matches: list[RuleMatch] = []
    for rule in _RULES:
        fired_kw = _first_match(text, rule["keywords"])
        if fired_kw is None:
            continue
        matches.append(
            RuleMatch(
                rule_id=rule["id"],
                contract_types=list(rule["contract_types"]),
                areas=list(rule["areas"]),
                severity=Severity(rule["severity"]),
                description=rule["description"],
                matched_keyword=fired_kw,
            )
        )

    logger.debug("Rules engine: %d rules fired on %d-char text", len(matches), len(text))
    return matches


def contracts_targeted_by_rules(matches: list[RuleMatch]) -> tuple[set[str], set[str]]:
    """Aggregate contract_types and areas across all rule matches.

    Args:
        matches: Output of apply_rules().

    Returns:
        (contract_types, areas) — two sets of strings.
    """
    types: set[str] = set()
    areas: set[str] = set()
    for m in matches:
        types.update(m.contract_types)
        areas.update(m.areas)
    return types, areas


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _first_match(text: str, patterns: list[str]) -> str | None:
    """Return the first pattern that matches, or None."""
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return pat
    return None
