import logging
import re

logger = logging.getLogger(__name__)

# Matches section/article headers in Spanish and English regulatory texts.
# Groups: keyword (Artículo, Section…) + identifier (number, roman numeral, ordinal).
_HEADER_RE = re.compile(
    r"(?:^|\n)"
    r"(?P<header>"
    r"(?:Art[íi]culo|ARTÍCULO|Artículo|Articulo|Article"
    r"|Secci[oó]n|SECCIÓN|Section"
    r"|Cap[íi]tulo|CAPÍTULO|Chapter"
    r"|Fracción|FRACCIÓN|Fraction"
    r"|Regla|Rule|Paragraph|Párrafo|PÁRRAFO"
    r")\s+"
    r"(?:\d+[\w\.]*|[IVXivx]+|[A-Z][a-z]+)"  # 5, 5o, 5 Bis, IV, Primero…
    r"[o\.\:\-]?"
    r")",
    re.MULTILINE,
)

_FALLBACK_SECTION = "__document__"


def split_into_sections(text: str) -> dict[str, str]:
    """Split a regulatory text into a dict keyed by section header.

    Identifies headers like "Artículo 5", "Section 3", "Capítulo II" and
    returns a mapping from normalised header → section body text.

    If no recognisable headers are found the entire text is returned under
    the key '__document__' so downstream code never receives an empty dict.

    Args:
        text: Plain text extracted from a regulatory document.

    Returns:
        Ordered dict {header: body_text}. The header is stripped and
        lower-cased to simplify comparison across document versions.
    """
    matches = list(_HEADER_RE.finditer(text))

    if not matches:
        logger.debug("No section headers found; treating document as single section")
        return {_FALLBACK_SECTION: text.strip()}

    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        header = _normalise_header(match.group("header"))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        # De-duplicate headers that appear twice (e.g. a section referenced
        # in an amendment also containing its full text)
        if header in sections:
            sections[header] += "\n" + body
        else:
            sections[header] = body

    logger.debug("Split into %d sections", len(sections))
    return sections


def _normalise_header(header: str) -> str:
    """Lower-case, collapse whitespace, strip trailing punctuation."""
    return re.sub(r"\s+", " ", header.strip().lower()).rstrip(".-:")
