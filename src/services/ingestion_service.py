import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseScraper, RawDocument
from src.ingestion.cnbv import CNBVScraper
from src.ingestion.sec import SECScraper
from src.parsing.pdf_parser import extract_text_from_pdf_bytes
from src.repositories import document_repo
from src.storage.local_storage import save_processed_text, save_raw_file

logger = logging.getLogger(__name__)

_SCRAPERS: dict[str, type[BaseScraper]] = {
    "cnbv": CNBVScraper,
    "sec": SECScraper,
}

SUPPORTED_SOURCES: list[str] = list(_SCRAPERS.keys())


@dataclass
class IngestionResult:
    source: str
    fetched: int = 0
    new: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


async def run(source_name: str, db: AsyncSession) -> IngestionResult:
    """Execute the full ingestion pipeline for one source.

    Pipeline per document:
        1. fetch_latest()      → list[RawDocument] (metadata)
        2. dedup check         → skip if already in DB
        3. fetch_document_text / fetch PDF bytes  → plain text
        4. save_raw_file()     → data/raw/<source>/
        5. save_processed_text()→ data/processed/<source>/
        6. create_from_raw()   → DB insert (committed by caller)

    Args:
        source_name: "cnbv" or "sec" (case-insensitive).
        db: Active async session; caller must commit after this returns.

    Returns:
        IngestionResult with counts and any error messages.
    """
    key = source_name.lower()
    if key not in _SCRAPERS:
        raise ValueError(f"Unknown source '{source_name}'. Valid: {SUPPORTED_SOURCES}")

    result = IngestionResult(source=key.upper())
    scraper = _SCRAPERS[key]()

    try:
        raw_docs = await scraper.fetch_latest()
    except Exception as exc:
        msg = f"fetch_latest() failed for {key}: {exc}"
        logger.error(msg)
        result.errors.append(msg)
        return result
    finally:
        await scraper.close()

    result.fetched = len(raw_docs)
    logger.info("%s: %d documents found in feed", key.upper(), result.fetched)

    scraper = _SCRAPERS[key]()
    try:
        for raw_doc in raw_docs:
            success = await _process_one(scraper, raw_doc, db, result)
            if success:
                result.new += 1
    finally:
        await scraper.close()

    logger.info(
        "%s ingestion done — new=%d skipped=%d failed=%d",
        key.upper(), result.new, result.skipped, result.failed,
    )
    return result


async def _process_one(
    scraper: BaseScraper,
    raw_doc: RawDocument,
    db: AsyncSession,
    result: IngestionResult,
) -> bool:
    """Process a single RawDocument through the full pipeline.

    Returns True if a new DB record was created, False otherwise.
    """
    existing = await document_repo.get_by_external_id(db, raw_doc.external_id)
    if existing is not None:
        logger.debug("Skipping already-known document: %s", raw_doc.external_id)
        result.skipped += 1
        return False

    raw_text, file_path_str = await _fetch_content(scraper, raw_doc)

    if not raw_text:
        msg = f"No text retrieved for {raw_doc.external_id}"
        logger.warning(msg)
        result.errors.append(msg)
        result.failed += 1
        return False

    await document_repo.create_from_raw(db, raw_doc, raw_text=raw_text, file_path=file_path_str)
    return True


async def _fetch_content(scraper: BaseScraper, raw_doc: RawDocument) -> tuple[str, str | None]:
    """Download and persist the document content.

    Tries PDF download first if the URL ends in .pdf, otherwise falls back to
    the scraper's HTML extraction. If both fail, returns the RSS description.

    Returns:
        (plain_text, file_path_str_or_None)
    """
    url = raw_doc.url or ""
    raw_text = ""
    file_path_str: str | None = None

    if url.lower().endswith(".pdf"):
        try:
            response = await scraper._get(url)
            pdf_bytes = response.content
            raw_text = extract_text_from_pdf_bytes(pdf_bytes)
            saved = save_raw_file(raw_doc.source, raw_doc.external_id, pdf_bytes, "pdf")
            file_path_str = str(saved)
        except Exception as exc:
            logger.warning("PDF fetch failed for %s: %s", raw_doc.external_id, exc)

    if not raw_text and url:
        try:
            raw_text = await scraper.fetch_document_text(url)
            if raw_text:
                saved_raw = save_raw_file(
                    raw_doc.source, raw_doc.external_id, raw_text.encode("utf-8"), "html"
                )
                file_path_str = str(saved_raw)
        except Exception as exc:
            logger.warning("HTML fetch failed for %s: %s", raw_doc.external_id, exc)

    if not raw_text and raw_doc.raw_text:
        raw_text = raw_doc.raw_text

    if raw_text:
        save_processed_text(raw_doc.source, raw_doc.external_id, raw_text)

    return raw_text, file_path_str
