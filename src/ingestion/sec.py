import logging
from datetime import datetime

import feedparser
from bs4 import BeautifulSoup

from src.ingestion.base import BaseScraper, RawDocument

logger = logging.getLogger(__name__)

SEC_RSS_RULES = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=rule&dateb=&owner=include&count=40&search_text=&output=atom"
SEC_RSS_PROPOSED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=proposed+rule&dateb=&owner=include&count=40&output=atom"


class SECScraper(BaseScraper):
    """Scrapes SEC Final Rules and Proposed Rules via EDGAR RSS feeds."""

    source_name = "SEC"

    _headers = {
        "User-Agent": "RegulatoryChangeAnalyzer contact@example.com",
        "Accept-Encoding": "gzip, deflate",
    }

    async def fetch_latest(self) -> list[RawDocument]:
        documents: list[RawDocument] = []
        for feed_url in [SEC_RSS_RULES, SEC_RSS_PROPOSED]:
            documents.extend(await self._fetch_feed(feed_url))
        logger.info("SEC: found %d entries", len(documents))
        return documents

    async def _fetch_feed(self, feed_url: str) -> list[RawDocument]:
        try:
            response = await self._get(feed_url, headers=self._headers)
            feed = feedparser.parse(response.text)
        except Exception as exc:
            logger.error("Failed to fetch SEC feed %s: %s", feed_url, exc)
            return []

        results: list[RawDocument] = []
        for entry in feed.entries:
            pub_date = self._parse_date(entry.get("updated", entry.get("published", "")))
            doc = RawDocument(
                external_id=f"SEC-{entry.get('id', '')[:100]}",
                source=self.source_name,
                title=entry.get("title", "No title"),
                url=entry.get("link", ""),
                publication_date=pub_date or datetime.utcnow(),
            )
            results.append(doc)
        return results

    async def fetch_document_text(self, url: str) -> str:
        """Fetch SEC rule page and extract filing text."""
        try:
            response = await self._get(url, headers=self._headers)
            soup = BeautifulSoup(response.text, "lxml")
            body = soup.find("div", class_="formContent") or soup.find("body")
            return body.get_text(separator="\n", strip=True) if body else ""
        except Exception as exc:
            logger.error("Failed to fetch SEC document %s: %s", url, exc)
            return ""

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        formats = ["%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %z"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
