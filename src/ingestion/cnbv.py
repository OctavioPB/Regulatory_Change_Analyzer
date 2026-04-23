import hashlib
import logging
from datetime import datetime

import feedparser
from bs4 import BeautifulSoup

from src.ingestion.base import BaseScraper, RawDocument

logger = logging.getLogger(__name__)

# DOF (Diario Oficial de la Federación) RSS — the official gazette for CNBV circulars
DOF_RSS_URL = "https://www.dof.gob.mx/rss.php"

_CNBV_KEYWORDS = [
    "CNBV", "Circular", "SOFOM", "Banca Múltiple", "Fintech",
    "CONDUSEF", "institución de crédito", "disposiciones de carácter general",
]


class CNBVScraper(BaseScraper):
    """Scrapes CNBV circulars and multi-banking rules from the DOF RSS feed."""

    source_name = "CNBV"

    async def fetch_latest(self) -> list[RawDocument]:
        """Parse DOF RSS and return entries related to CNBV regulations."""
        try:
            response = await self._get(DOF_RSS_URL)
            feed = feedparser.parse(response.text)
        except Exception as exc:
            logger.error("Failed to fetch DOF RSS: %s", exc)
            return []

        documents: list[RawDocument] = []
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            if not self._is_cnbv_entry(title):
                continue

            link = entry.get("link", "")
            # Use a stable hash of the URL so external_id is collision-free
            url_hash = hashlib.sha1(link.encode()).hexdigest()[:12]
            pub_date = self._parse_date(entry.get("published", ""))

            documents.append(RawDocument(
                external_id=f"CNBV-{url_hash}",
                source=self.source_name,
                title=title,
                url=link,
                publication_date=pub_date or datetime.utcnow(),
                # Populate raw_text from RSS summary so we have *something* even if
                # the full-page fetch later fails.
                raw_text=BeautifulSoup(summary, "lxml").get_text(" ", strip=True) if summary else None,
            ))

        logger.info("CNBV: %d relevant entries found", len(documents))
        return documents

    async def fetch_document_text(self, url: str) -> str:
        """Extract plain text from a DOF publication page.

        The DOF wraps the regulatory text inside <div id="DivDecreto">.
        Falls back to full <body> if that div is absent.
        """
        try:
            response = await self._get(url)
            soup = BeautifulSoup(response.text, "lxml")
            content = soup.find("div", id="DivDecreto") or soup.find("body")
            return content.get_text(separator="\n", strip=True) if content else ""
        except Exception as exc:
            logger.error("Failed to fetch DOF page %s: %s", url, exc)
            return ""

    @staticmethod
    def _is_cnbv_entry(title: str) -> bool:
        return any(kw.lower() in title.lower() for kw in _CNBV_KEYWORDS)

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%a, %d %b %Y %H:%M:%S GMT",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
