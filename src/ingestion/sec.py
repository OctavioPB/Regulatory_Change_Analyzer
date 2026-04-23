import logging
from datetime import datetime

import feedparser
from bs4 import BeautifulSoup

from src.ingestion.base import BaseScraper, RawDocument

logger = logging.getLogger(__name__)

# SEC press releases RSS — reliable, updated daily, covers Final Rules & Proposed Rules
SEC_PRESS_RSS = "https://www.sec.gov/rss/news/press.xml"

# Keywords that indicate a regulatory rule entry (not enforcement or corporate news)
_RULE_KEYWORDS = [
    "final rule", "proposed rule", "interim final rule",
    "proposes rule", "adopting", "adopts",
    "amends", "regulation", "rulemaking",
]

# Required header per SEC EDGAR terms of service
_HEADERS = {
    "User-Agent": "RegulatoryChangeAnalyzer/0.1 portfolio-project tavoriddler@gmail.com",
    "Accept-Encoding": "gzip, deflate",
}


class SECScraper(BaseScraper):
    """Scrapes SEC Final Rules and Proposed Rules via the SEC press releases RSS feed."""

    source_name = "SEC"

    async def fetch_latest(self) -> list[RawDocument]:
        """Parse the SEC press release feed and return entries related to rulemaking."""
        try:
            response = await self._get(SEC_PRESS_RSS, headers=_HEADERS)
            feed = feedparser.parse(response.text)
        except Exception as exc:
            logger.error("Failed to fetch SEC RSS: %s", exc)
            return []

        documents: list[RawDocument] = []
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            if not self._is_rule_entry(title, summary):
                continue

            pub_date = self._parse_date(entry.get("published", entry.get("updated", "")))
            entry_id = entry.get("id", entry.get("link", ""))

            documents.append(RawDocument(
                external_id=f"SEC-{entry_id[-80:]}",
                source=self.source_name,
                title=title,
                url=entry.get("link", ""),
                publication_date=pub_date or datetime.utcnow(),
                raw_text=BeautifulSoup(summary, "lxml").get_text(" ", strip=True) if summary else None,
            ))

        logger.info("SEC: %d rule-related entries found", len(documents))
        return documents

    async def fetch_document_text(self, url: str) -> str:
        """Download a SEC press release page and extract its main body text."""
        try:
            response = await self._get(url, headers=_HEADERS)
            soup = BeautifulSoup(response.text, "lxml")
            # SEC press release pages wrap content in <div class="article-body"> or <article>
            body = (
                soup.find("div", class_="article-body")
                or soup.find("article")
                or soup.find("div", id="main-content")
                or soup.find("body")
            )
            return body.get_text(separator="\n", strip=True) if body else ""
        except Exception as exc:
            logger.error("Failed to fetch SEC document %s: %s", url, exc)
            return ""

    @staticmethod
    def _is_rule_entry(title: str, summary: str) -> bool:
        combined = (title + " " + summary).lower()
        return any(kw in combined for kw in _RULE_KEYWORDS)

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
