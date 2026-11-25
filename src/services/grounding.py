"""Citation validation and the system-written refusal (lessons from Legal_AI_Assistant, ADR-007).

* The refusal is a **system action**: when nothing was retrieved, or when the model declines, the
  user gets a fixed text written by code. The model is never trusted to phrase it, and its own
  prose refusal is discarded.
* Every answer is checked by a pure function before it is final: each ``[REG-n]``/``[CON-n]`` tag
  must be one of the sources shown to the model, example markers copied from a prompt
  (``[REG-N]``) are rejected, and an answer needs at least one valid citation. A failing answer
  is regenerated **once** with feedback written by code; if it fails again the system refuses.

The validator proves provenance, not faithfulness: a valid tag on a wrong paraphrase passes.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

MAX_REGENERATIONS = 1

REFUSAL_EN = (
    "The documents in the system don't contain sufficient information about this topic. "
    "I recommend consulting the original source directly."
)
REFUSAL_ES = (
    "Los documentos del sistema no contienen información suficiente sobre este tema. "
    "Recomiendo consultar directamente la fuente original."
)

# REG-3 / CON-12 are citations; REG-N, CON-X, REG-n are markers copied from an example
_TAG_RE = re.compile(r"\b(REG|CON)-([A-Za-z0-9]+)\b")

# Phrases that read as "the sources don't answer this" (accents and case folded)
_REFUSAL_MARKERS = (
    "don't contain sufficient information", "do not contain sufficient information",
    "does not contain sufficient information", "doesn't contain sufficient information",
    "not contain enough information", "no information about", "could not find", "couldn't find",
    "does not contain information", "do not contain information", "does not contain the answer",
    "no contienen informacion suficiente", "no contiene informacion suficiente",
    "no contienen informacion", "no contiene informacion", "no encontre", "no se encontro",
    "no hay informacion",
)

_SPANISH_HINTS = {
    "que", "cual", "cuales", "como", "cuando", "donde", "cuanto", "cuantos", "para", "las", "los",
    "del", "por", "con", "una", "este", "esta", "debe", "deben", "contratos", "circular", "plazo",
}


def fold(text: str) -> str:
    """Lowercase and strip accents."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def is_spanish(question: str) -> bool:
    """Cheap language guess for the refusal text: Spanish punctuation, accents or function words."""
    if any(ch in question for ch in "¿¡ñÑáéíóúÁÉÍÓÚ"):
        return True
    words = re.findall(r"[a-z]+", fold(question))
    return sum(w in _SPANISH_HINTS for w in words) >= 2


def refusal_text(question: str) -> str:
    return REFUSAL_ES if is_spanish(question) else REFUSAL_EN


def looks_like_refusal(answer: str) -> bool:
    folded = fold(answer).replace("’", "'")
    return any(m in folded for m in _REFUSAL_MARKERS)


@dataclass(frozen=True)
class Verdict:
    cited: tuple[str, ...]         # valid tags, in order of first appearance
    invalid: tuple[str, ...]       # well-formed tags that were never shown to the model
    placeholders: tuple[str, ...]  # example markers (REG-N) copied from a prompt
    empty: bool                    # no answer text at all
    refused: bool                  # no valid citation and the text reads as "not in the sources"

    @property
    def grounded(self) -> bool:
        return not self.empty and not self.refused and bool(self.cited) \
            and not self.invalid and not self.placeholders


def validate(answer: str, valid_tags: Iterable[str]) -> Verdict:
    """Check an answer's citations against the tags of the sources the model was shown."""
    valid = set(valid_tags)
    cited: list[str] = []
    invalid: list[str] = []
    placeholders: list[str] = []
    for prefix, ident in _TAG_RE.findall(answer or ""):
        tag = f"{prefix}-{ident}"
        bucket = (cited if tag in valid else invalid) if ident.isdigit() else placeholders
        if tag not in bucket:
            bucket.append(tag)
    empty = not (answer or "").strip()
    refused = not empty and not cited and looks_like_refusal(answer)
    return Verdict(tuple(cited), tuple(invalid), tuple(placeholders), empty, refused)


def needs_regeneration(v: Verdict) -> bool:
    """A declined answer goes straight to the system refusal; any other ungrounded one is retried."""
    return not v.grounded and not v.refused


def feedback(v: Verdict, valid_tags: Iterable[str]) -> str:
    """Correction written by code from the verdict (never by a model)."""
    tags = list(dict.fromkeys(valid_tags))  # source order, deduped
    lines = ["Your previous answer broke the citation rules. Fix only what is listed:"]
    if v.empty:
        lines.append("- You did not write an answer.")
    if v.invalid:
        lines.append(f"- You cited tags that are not in the sources: {', '.join(v.invalid)}.")
    if v.placeholders:
        lines.append(f"- You copied example markers instead of real tags: {', '.join(v.placeholders)}.")
    if not v.cited and not v.empty:
        lines.append("- You did not cite any source.")
    lines.append(
        "Write the complete answer again, citing only these tags: " + (", ".join(tags) or "(none)") + "."
    )
    lines.append("If the sources do not answer the question, say only that the documents don't "
                 "contain sufficient information.")
    return "\n".join(lines)
