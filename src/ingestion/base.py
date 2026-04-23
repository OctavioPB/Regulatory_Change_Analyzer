import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class RawDocument:
    """Minimal payload returned by any scraper before DB persistence."""

    external_id: str
    source: str
    title: str
    url: str
    publication_date: datetime
    raw_text: str | None = None
    file_path: str | None = None


class BaseScraper(ABC):
    """Abstract base for all regulatory source scrapers."""

    source_name: str = ""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    @abstractmethod
    async def fetch_latest(self) -> list[RawDocument]:
        """Return documents published since the last run."""

    @abstractmethod
    async def fetch_document_text(self, url: str) -> str:
        """Download and extract plain text from a single document URL."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, url: str, **kwargs) -> httpx.Response:
        """HTTP GET with automatic retry on transient errors."""
        logger.debug("GET %s", url)
        response = await self._client.get(url, **kwargs)
        response.raise_for_status()
        return response

    async def close(self) -> None:
        await self._client.aclose()
