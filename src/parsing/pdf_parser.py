import io
import logging
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str | Path) -> str:
    """Extract plain text from a PDF file.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        Concatenated plain text from all pages.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        logger.error("Failed to extract text from %s: %s", path, exc)
        raise

    text = "\n".join(pages)
    logger.debug("Extracted %d chars from %s (%d pages)", len(text), path.name, len(reader.pages))
    return text


def extract_text_from_pdf_bytes(data: bytes) -> str:
    """Extract plain text from raw PDF bytes (e.g., from an HTTP response).

    Args:
        data: Raw PDF content.

    Returns:
        Concatenated plain text.
    """
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        logger.error("Failed to extract text from PDF bytes: %s", exc)
        raise

    return "\n".join(pages)
