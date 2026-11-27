"""Change-detection cases built from real SEC rule amendments (17 CFR), via the eCFR.

Each case compares a CFR section the day before an amendment took effect with the day it did.
Built into frozen fixtures by ``python -m evals.change_detection build`` (texts are US government
works, public domain) and graded by ``python -m evals.change_detection run``.

Ground truth has two parts:

* **computed** at build time — which paragraphs were added, removed or modified, aligned by their
  official labels ((a), (b)(2), …). It uses none of the app's NLP code.
* **annotated** here — ``facts``: phrases that must appear on the old / new side of a reported
  change, checked against the fixture text when it is built; ``change_types``: the classifications
  judged acceptable. Facts are verbatim from the eCFR; change types are developer judgment, not
  lawyer-reviewed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SEC = "securities-and-exchange-commission"


@dataclass(frozen=True)
class Fact:
    old: str | None = None   # must be in the old text of a reported change (None: no check)
    new: str | None = None   # must be in the new text of the same change


@dataclass(frozen=True)
class EcfrCase:
    id: str
    section: str                     # "240.15c6-1"
    after: str                       # date the amendment took effect (an eCFR version date)
    before: str | None = None        # default: the day before ``after``
    title: int = 17
    agency: str = SEC
    substantive: bool = True         # False → control: the app must report no change
    facts: tuple[Fact, ...] = ()
    change_types: frozenset[str] = field(default_factory=frozenset)
    note: str = ""


CASES: list[EcfrCase] = [
    EcfrCase(
        "tplus1-2023", "240.15c6-1", "2023-05-05",
        facts=(Fact("later than the second business day", "later than the first business day"),
               Fact("later than the fourth business day", "later than the second business day"),
               Fact(None, "Security-based swaps")),
        change_types=frozenset({"deadline", "limit_modification"}),
        note="T+2 → T+1 (Release 34-96930, compliance date 2024-05-28); firm-commitment T+4 → T+2.",
    ),
    EcfrCase(
        "tplus2-2017", "240.15c6-1", "2017-03-29",
        facts=(Fact("later than the third business day", "later than the second business day"),),
        change_types=frozenset({"deadline", "limit_modification"}),
        note="T+3 → T+2. A one-word change in a long paragraph.",
    ),
    EcfrCase(
        "marketing-rule-2021", "275.206(4)-1", "2021-03-05",
        facts=(Fact("Which refers, directly or indirectly, to any testimonial", None),
               Fact(None, "General prohibitions. An advertisement may not:"),
               Fact(None, "Any hypothetical performance unless the investment adviser")),
        change_types=frozenset({"new_requirement"}),
        note="Advertising rule replaced by the Marketing Rule (compliance date 2022-11-04): 7 → 115 paragraphs.",
    ),
    EcfrCase(
        "rule-10b5-1-2023", "240.10b5-1", "2023-02-27",
        facts=(Fact(None, "cooling-off period"),),
        change_types=frozenset({"new_requirement", "deadline"}),
        note="Affirmative-defense conditions for trading plans: cooling-off periods, certifications.",
    ),
    EcfrCase(
        "schedule-13d-2024", "240.13d-1", "2024-02-05",
        facts=(Fact("within 10 days after the acquisition", "within five business days after the date of the acquisition"),
               Fact("45 days after the end of the calendar year", "45 days after the end of the calendar quarter")),
        change_types=frozenset({"deadline"}),
        note="Beneficial-ownership reporting deadlines shortened.",
    ),
    EcfrCase(
        "names-rule-2023", "270.35d-1", "2023-12-11",
        facts=(Fact(None, "at least quarterly"),),
        change_types=frozenset({"new_requirement"}),
        note="Fund Names Rule: 80% policy broadened, quarterly review, notice requirements.",
    ),
    EcfrCase(
        "electronic-records-2023", "240.17a-4", "2023-01-04",
        facts=(Fact(None, "complete time-stamped audit trail"),
               Fact(None, "The term designated executive officer means")),
        change_types=frozenset({"new_requirement"}),
        note="Audit-trail alternative to WORM storage; designated executive officer / third party.",
    ),
    EcfrCase(
        "control-reissue-2022", "275.206(4)-1", "2022-11-14", substantive=False,
        note="Non-substantive eCFR reissue: identical text, the app must report nothing.",
    ),
    EcfrCase(
        "control-stable-15c6-1", "240.15c6-1", "2022-12-31", before="2020-01-02", substantive=False,
        note="No version between these dates: identical text, the app must report nothing.",
    ),
]
