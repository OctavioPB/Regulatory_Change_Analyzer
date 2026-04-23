import logging
import re
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

_SAFE_ID_RE = re.compile(r"[^\w\-]")


def _safe_filename(external_id: str) -> str:
    """Convert an arbitrary external_id into a filesystem-safe filename stem."""
    return _SAFE_ID_RE.sub("_", external_id)[:120]


def save_raw_file(source: str, external_id: str, content: bytes, extension: str) -> Path:
    """Write raw downloaded content (HTML, PDF, …) to data/raw/<source>/.

    Args:
        source: Source name, e.g. "CNBV" or "SEC".
        external_id: Unique document identifier used as filename.
        content: Raw bytes to persist.
        extension: File extension without the dot, e.g. "html" or "pdf".

    Returns:
        Path of the written file.
    """
    dest_dir = settings.raw_dir / source.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{_safe_filename(external_id)}.{extension}"
    dest.write_bytes(content)
    logger.debug("Saved raw file: %s (%d bytes)", dest, len(content))
    return dest


def save_processed_text(source: str, external_id: str, text: str) -> Path:
    """Write extracted plain text to data/processed/<source>/.

    Args:
        source: Source name.
        external_id: Unique document identifier.
        text: Plain text extracted from the document.

    Returns:
        Path of the written file.
    """
    dest_dir = settings.processed_dir / source.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{_safe_filename(external_id)}.txt"
    dest.write_text(text, encoding="utf-8")
    logger.debug("Saved processed text: %s (%d chars)", dest, len(text))
    return dest


def load_processed_text(source: str, external_id: str) -> str | None:
    """Load previously processed text from disk, or None if not found.

    Args:
        source: Source name.
        external_id: Unique document identifier.

    Returns:
        Stored plain text or None.
    """
    path = settings.processed_dir / source.lower() / f"{_safe_filename(external_id)}.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
