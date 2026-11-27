"""Change-detection cases built from real Mexican law reforms (DOF), via Diputados + Internet Archive.

Each case compares a law's consolidated text (Cámara de Diputados, archived by the Internet Archive)
just before and just after one DOF reform decree; the capture interval contains exactly that decree.
Built by ``python -m evals.change_detection build`` alongside the eCFR cases.

Ground truth: the articles the decree lists for this law (official), cross-checked against the
articles whose wording changed between the two texts. ``facts`` are verbatim phrases (checked at build
time, whitespace-insensitive because the PDF text layer splits words); ``change_types`` are developer
judgment, not lawyer-reviewed.

The July 2025 AML-law (LFPIORPI) reform is not included: no archived copy of the consolidated text
between the 2021 and 2025 reforms exists, so the "before" text cannot be obtained.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from evals.ecfr_cases import Fact


@dataclass(frozen=True)
class MxCase:
    id: str
    law: str                      # Diputados file name: "LMV" → LeyesBiblio/pdf/LMV.pdf
    slug: str                     # reform page: LeyesBiblio/ref/<slug>.htm
    before: str                   # archive timestamp prefix (YYYYMMDD) of the "before" capture
    after: str
    decree: str | None = None     # DOF date tag in the decree file name: "14nov25"; None → control
    facts: tuple[Fact, ...] = ()
    change_types: frozenset[str] = field(default_factory=frozenset)
    note: str = ""

    @property
    def substantive(self) -> bool:
        return self.decree is not None


HOMOLOGATION = Fact("Código Federal de Procedimientos Civiles", "Código Nacional de Procedimientos Civiles")

CASES: list[MxCase] = [
    MxCase(
        "mx-lmv-homologacion-2025", "LMV", "lmv", "20241221", "20251212", "14nov25",
        facts=(HOMOLOGATION,), change_types=frozenset({"other", "clarification"}),
        note="DOF 14-11-2025: one reference updated (art. 389, third paragraph) in a 234-page law.",
    ),
    MxCase(
        "mx-lritf-homologacion-2025", "LRITF", "lritf", "20240127", "20251209", "14nov25",
        facts=(HOMOLOGATION,), change_types=frozenset({"other", "clarification"}),
        note="DOF 14-11-2025, same decree: Ley Fintech art. 102, third paragraph.",
    ),
    MxCase(
        "mx-lic-procedimiento-2024", "LIC", "lic", "20220928", "20240127", "24ene24",
        facts=(Fact("Protección al Ahorro Bancario, en el ámbito",
                    "Protección al Ahorro Bancario y el Banco de México, en el ámbito"),
               Fact(None, "Las notificaciones, trámite y resolución del recurso de reconsideración se regirán por la Ley del Banco de México")),
        change_types=frozenset({"new_requirement", "clarification"}),
        note="DOF 24-01-2024 (financial laws, administrative procedure): arts. 48 Bis 1, 107 Bis, 109 Bis 1.",
    ),
    MxCase(
        "mx-lgoaac-almacenes-2024", "LGOAAC", "lgoaac", "20240127", "20240531", "26mar24",
        facts=(Fact("podrán tener en arrendamiento o en habilitación", "podrán tener en arrendamiento, en comodato o en habilitación"),
               Fact(None, "La Secretaría de Economía deberá determinar mediante disposiciones de carácter general")),
        change_types=frozenset({"new_requirement"}),
        note="DOF 26-03-2024: general deposit warehouses regime, 12 articles incl. new 22 Bis 12.",
    ),
    MxCase(
        "mx-cff-improcedencia-2025", "CFF", "cff", "20250404", "20251018", "16oct25",
        facts=(Fact(None, "Que el contribuyente manifieste desconocer"),),
        change_types=frozenset({"new_requirement"}),
        note="DOF 16-10-2025: three new grounds of inadmissibility (art. 124, fracciones X-XII).",
    ),
    MxCase(
        "mx-control-lgoaac-2024a", "LGOAAC", "lgoaac", "20240531", "20240910",
        note="Two archived copies with no reform in between: the app must report nothing.",
    ),
    MxCase(
        "mx-control-lgoaac-2024b", "LGOAAC", "lgoaac", "20240910", "20241031",
        note="Same, another pair of copies (the PDF was regenerated: different bytes, same law).",
    ),
]
