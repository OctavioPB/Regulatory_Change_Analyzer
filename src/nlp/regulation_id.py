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
    numbered = _NUMBERED.search(folded)
    unica = _UNICA.search(folded)
    if numbered and (not unica or numbered.start() < unica.start()):
        return f"circular:{int(numbered.group(1))}/{numbered.group(2)}"
    if unica:
        return f"circular-unica:{unica.group(1)}"
    return None


def title_prefilter(key: str) -> str:
    """ILIKE pattern that every title with ``key`` matches (candidates are re-checked in Python)."""
    if key.startswith("circular:"):
        number, year = key.removeprefix("circular:").split("/")
        return f"%{number}%/%{year}%"
    return "%circular%"
