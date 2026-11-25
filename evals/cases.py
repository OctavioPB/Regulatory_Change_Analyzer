"""Golden cases for the LLM features, over the synthetic demo data.

Corpus: the three synthetic CNBV circulars in ``scripts/seed_cnbv.py`` and the
six demo contracts from ``POST /contracts/seed``. Every expected fact below is
literally in that text, so a case can be graded by code — no LLM judge.

``facts`` is a list of groups; a group passes when ANY of its alternatives
appears in the normalised answer (accents folded, lower-case, digit
separators removed). Cases are written by the developer, not reviewed by a
compliance lawyer: treat results as a comparison between models on the same
set, not as a quality certification.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QACase:
    id: str
    question: str
    facts: list[list[str]] = field(default_factory=list)
    answerable: bool = True
    # Multi-step questions are only asked to the research agent
    agent_only: bool = False


QA_CASES: list[QACase] = [
    QACase(
        "sofom-limit-es",
        "¿A qué porcentaje del capital neto se reduce el límite de contraparte para las SOFOM "
        "según la Circular 12/2025?",
        facts=[["15%", "15 %", "quince por ciento"]],
    ),
    QACase(
        "sofom-deadline-en",
        "How many days do credit institutions have to adjust their risk management systems "
        "to the new SOFOM counterparty limit?",
        facts=[["90", "noventa", "ninety"]],
    ),
    QACase(
        "aml-threshold-en",
        "What is the unusual-transaction reporting threshold for electronic operations of "
        "fintech institutions (ITF)?",
        facts=[["100000", "cien mil", "100k"]],
    ),
    QACase(
        "aml-officer-es",
        "¿En qué plazo deben las ITF designar un oficial de cumplimiento certificado en PLD?",
        facts=[["180", "ciento ochenta"]],
    ),
    QACase(
        "basel-ccn-es",
        "¿Cuál es el nuevo coeficiente de capital neto mínimo para la banca múltiple y cuál era el anterior?",
        facts=[["12%", "12 %", "doce por ciento"], ["10.5", "10,5", "diez punto cinco"]],
    ),
    QACase(
        "unanswerable-crypto-es",
        "¿Qué límites estableció la CNBV para invertir en criptoactivos dentro de las AFORES?",
        answerable=False,
    ),
    QACase(
        "unanswerable-sec-en",
        "What did the SEC's 2025 rule on climate disclosures require from Mexican SOFOMs?",
        answerable=False,
    ),
    # Needs chaining: find the circular → its impact alerts → the affected contracts.
    QACase(
        "multihop-aml-contracts-es",
        "¿Qué contratos internos se ven afectados por la Circular 15/2025 de PLD para fintech, "
        "y qué cláusula de cada uno habría que revisar?",
        # The two AML-relevant contracts the rules engine maps for Artículos 1 and 3
        facts=[["client onboarding"], ["electronic payment"]],
        agent_only=True,
    ),
    QACase(
        "multihop-sofom-derivatives-en",
        "Circular 12/2025 mentions derivatives master agreements with SOFOMs. Which of our contracts "
        "is that, and what does its relevant clause currently say about leverage?",
        facts=[["isda"], ["8.2", "6.1"]],
        agent_only=True,
    ),
]

# Phrases that count as a proper "the documents don't say" answer
REFUSAL_MARKERS = [
    "don't contain sufficient", "do not contain sufficient", "does not contain", "don't contain",
    "no information", "not contain information", "insufficient information", "no contienen",
    "no contiene", "no hay informacion", "no encontre", "no se encontro", "no dispongo",
    "informacion suficiente", "no cuento con", "not found", "could not find", "no aparece",
    "no existe informacion", "no incluye", "no se menciona", "not mentioned", "no mention",
]

# Addendum structure checks: (label, alternatives that must appear, case-insensitive)
ADDENDUM_SECTIONS = [
    ("recitals", ["whereas", "considerando"]),
    ("operative", ["now therefore", "por lo tanto"]),
    ("articles", ["article", "artículo", "articulo"]),
    ("general_provisions", ["general provisions", "full force and effect", "disposiciones generales"]),
    ("signature", ["in witness whereof", "signature", "firma", "party a"]),
]
