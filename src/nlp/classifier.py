import difflib
import logging
import re

from src.models.document import ChangeType

logger = logging.getLogger(__name__)

# Keyword sets for rule-based classification (Sprint 2 baseline)
_RULES: list[tuple[ChangeType, list[str]]] = [
    (ChangeType.repeal, ["deroga", "derogado", "repeal", "repealed", "abrogat"]),
    (ChangeType.new_requirement, ["nuevo", "nueva", "adiciona", "new requirement", "shall now", "must", "deben", "deberán", "obligatorio", "obligatoria", "required to"]),
    (ChangeType.limit_modification, ["límite", "limite", "umbral", "threshold", "limit", "porcentaje", "percentage", "%"]),
    (ChangeType.deadline, ["plazo", "fecha límite", "deadline", "within", "no later than", "a más tardar"]),
    (ChangeType.clarification, ["aclara", "precisa", "clarif", "means", "defined as", "se entiende"]),
]


def classify_change(text: str) -> ChangeType:
    """Rule-based classification of a regulatory change text.

    Uses keyword matching as a Sprint 2 baseline; replace with a fine-tuned
    Legal-BERT classifier once training data is available.

    Args:
        text: Plain text of the changed provision.

    Returns:
        The most likely ChangeType, defaulting to ChangeType.other.
    """
    text_lower = text.lower()
    for change_type, keywords in _RULES:
        if any(kw in text_lower for kw in keywords):
            logger.debug("Classified as %s (keyword match)", change_type.value)
            return change_type

    logger.debug("Classification defaulted to 'other'")
    return ChangeType.other


# ── Modified provisions: classify what changed, not the whole text ───────────
# Whole-text keywords fire on boilerplate: almost every provision says "shall"/"must"/"deberán",
# so "within 10 days" → "within five business days" came out as new_requirement (eCFR eval).

_TOKEN_RE = re.compile(r"\w+|[%$€]")
_CONTEXT = 4             # words of context around each edit
_TARGETED_EDIT = 40      # changed tokens up to which an edit counts as targeted
_AMOUNT = re.compile(
    r"%|\$|€|\bmxn\b|\busd\b|\bpesos?\b|\bdollars?\b|\bpercent\b|\bpor ciento\b|\bumas?\b"
)
_PERIOD = re.compile(
    r"\b(?:days?|months?|years?|quarters?|weeks?|d[ií]as?|meses|mes|años?|trimestres?|semanas?)\b"
    r"|\bplazo\b|\bdeadline\b|\bno later than\b|\ba más tardar\b|\bwithin\b|\bdentro de\b"
)


def classify_modification(old_text: str, new_text: str) -> ChangeType:
    """Classify a modified provision by its edits (plus a few words of context).

    Targeted edits: an amount or percentage changed → limit_modification; a time period changed →
    deadline; otherwise the keyword rules on the edited words only — a reference update stays
    "other" instead of inheriting a "plazo" that the provision always had. Large edits that mostly
    add text → new_requirement; other large rewrites fall back to the whole-text rules.
    """
    old_tokens = _TOKEN_RE.findall(old_text.lower())
    new_tokens = _TOKEN_RE.findall(new_text.lower())
    edits = [op for op in difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False).get_opcodes()
             if op[0] != "equal"
             # a word split by the PDF text layer ("fo ndo" → "fondo") is not an edit
             and "".join(old_tokens[op[1]:op[2]]) != "".join(new_tokens[op[3]:op[4]])]
    changed = sum(max(i2 - i1, j2 - j1) for _, i1, i2, j1, j2 in edits)
    if not edits:
        return classify_change(new_text + "\n" + old_text)
    if changed > _TARGETED_EDIT:
        inserted = sum(j2 - j1 for _, _, _, j1, j2 in edits)
        deleted = sum(i2 - i1 for _, i1, i2, _, _ in edits)
        if inserted >= 3 * max(deleted, 1):  # e.g. new fracciones added to an article
            return ChangeType.new_requirement
        return classify_change(new_text + "\n" + old_text)

    core = " ".join(" ".join(old_tokens[i1:i2] + new_tokens[j1:j2]) for _, i1, i2, j1, j2 in edits)
    context = " ".join(
        " ".join(old_tokens[max(0, i1 - _CONTEXT):i2 + _CONTEXT] + new_tokens[max(0, j1 - _CONTEXT):j2 + _CONTEXT])
        for _, i1, i2, j1, j2 in edits
    )
    if _AMOUNT.search(core) or (re.search(r"\d", core) and _AMOUNT.search(context)):
        return ChangeType.limit_modification
    if _PERIOD.search(context):
        return ChangeType.deadline
    return classify_change(core)
