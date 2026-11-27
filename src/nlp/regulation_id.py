"""Which regulation a publication belongs to, so diffs compare versions of the *same* rule.

A document is only diffed against an earlier one with the same key. A title without a
recognisable identifier gets no key and is analysed on its own: comparing it with whatever
the source published last would report the other rule's articles as "removed (repeal)".
"""
import re
import unicodedata

# "Circular 12/2025", "Circular CNBV 7/2026", "CIRCULAR No. 3/2024", "Circular Núm. 14/2023"
_NUMBERED = re.compile(
    r"\bcircular\s+(?:(?:cnbv|no|num|numero)\.?\s+)*(\d{1,4})\s*/\s*(\d{4})\b"
)
# "Circular Única de Bancos" (CUB), "Circular Única de Emisoras" — amended in place, no number
_UNICA = re.compile(r"\bcircular\s+unica\s+de\s+([a-z]+)")
# US federal rules: "17 CFR 240.15c6-1", "17 C.F.R. § 275.206(4)-1", "17 CFR 240.17Ad-22"
_CFR = re.compile(r"\b(\d{1,2})\s*c\.?\s*f\.?\s*r\.?\s*(?:§+\s*)?(\d{1,4}\.\d[\w()\-]*)")


def _fold(text: str) -> str:
    """Lowercase and strip accents, so "Núm." and "Única" match their unaccented spellings."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def regulation_key(title: str) -> str | None:
    """Stable identifier of the regulation a title refers to, or ``None`` if it names none.

    The first identifier in the title wins, so "Resolución que modifica la Circular 12/2025"
    is matched to Circular 12/2025 itself.
    """
    folded = _fold(title)
    found: list[tuple[int, str]] = []
    if m := _NUMBERED.search(folded):
        found.append((m.start(), f"circular:{int(m.group(1))}/{m.group(2)}"))
    if m := _UNICA.search(folded):
        found.append((m.start(), f"circular-unica:{m.group(1)}"))
    if m := _CFR.search(folded):
        section = m.group(2).rstrip(".,;:-")
        found.append((m.start(), f"cfr:{int(m.group(1))}:{section}"))
    return min(found)[1] if found else None


def title_prefilter(key: str) -> str:
    """ILIKE pattern that every title with ``key`` matches (candidates are re-checked in Python)."""
    if key.startswith("circular:"):
        number, year = key.removeprefix("circular:").split("/")
        return f"%{number}%/%{year}%"
    if key.startswith("cfr:"):
        section = key.split(":", 2)[2]
        # "_" and "%" never occur in CFR section numbers; ILIKE is case-insensitive ("17Ad-22")
        return f"%{section}%"
    return "%circular%"
