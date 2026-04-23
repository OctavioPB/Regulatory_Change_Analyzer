import logging
import re
from datetime import datetime

import feedparser
from bs4 import BeautifulSoup

from src.ingestion.base import BaseScraper, RawDocument

logger = logging.getLogger(__name__)

CNBV_RSS_URL = "https://www.cnbv.gob.mx/Normatividad/Paginas/Disposiciones-de-caracter-general.aspx"
CNBV_DOF_RSS = "https://www.dof.gob.mx/rss.php"


class CNBVScraper(BaseScraper):
    """Scrapes CNBV circulars and multi-banking rules from DOF RSS feed."""

    source_name = "CNBV"

    async def fetch_latest(self) -> list[RawDocument]:
        """Parse DOF RSS and filter entries mentioning CNBV."""
        try:
            response = await self._get(CNBV_DOF_RSS)
            feed = feedparser.parse(response.text)
        except Exception as exc:
            logger.error("Failed to fetch CNBV RSS: %s", exc)
            return []

        documents: list[RawDocument] = []
        for entry in feed.entries:
            if not self._is_cnbv_entry(entry.get("title", "")):
                continue
            pub_date = self._parse_date(entry.get("published", ""))
            doc = RawDocument(
                external_id=f"CNBV-{entry.get('id', entry.get('link', ''))[:100]}",
                source=self.source_name,
                title=entry.get("title", "Sin título"),
                url=entry.get("link", ""),
                publication_date=pub_date or datetime.utcnow(),
            )
            documents.append(doc)

        logger.info("CNBV: found %d relevant entries", len(documents))
        return documents

    async def fetch_document_text(self, url: str) -> str:
        """Extract plain text from a DOF HTML page."""
        try:
            response = await self._get(url)
            soup = BeautifulSoup(response.text, "lxml")
            # DOF pages contain the regulatory text inside <div id="DivDecreto">
            content_div = soup.find("div", id="DivDecreto") or soup.find("body")
            return content_div.get_text(separator="\n", strip=True) if content_div else ""
        except Exception as exc:
            logger.error("Failed to fetch document text from %s: %s", url, exc)
            return ""

    @staticmethod
    def _is_cnbv_entry(title: str) -> bool:
        keywords = ["CNBV", "Circular", "SOFOM", "Banca Múltiple", "Fintech", "CONDUSEF"]
        return any(kw.lower() in title.lower() for kw in keywords)

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        formats = ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
